"""Fetch article lifecycle dates from PubMed and aggregate journal timelines.

Usage examples:
  python fetch_pubmed.py --pmids 38912345,38899110
  python fetch_pubmed.py --query "BMC Public Health[Journal] 2024[dp]" --limit 50

The script writes JSON to stdout. It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "asrarsaa@gmail.com"


@dataclass
class ArticleTiming:
    pmid: str
    journal: str
    issn: str | None
    received: date | None
    accepted: date | None
    published: date | None

    @property
    def submission_to_acceptance(self) -> int | None:
        if self.received and self.accepted and self.accepted >= self.received:
            return (self.accepted - self.received).days
        return None

    @property
    def acceptance_to_publication(self) -> int | None:
        if self.accepted and self.published and self.published >= self.accepted:
            return (self.published - self.accepted).days
        return None

    @property
    def submission_to_publication(self) -> int | None:
        if self.received and self.published and self.published >= self.received:
            return (self.published - self.received).days
        return None


def request_json(path: str, params: dict[str, str | int]) -> dict:
    params = {**params, "tool": "journal-timelines", "email": EMAIL, "retmode": "json"}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def request_xml(path: str, params: dict[str, str | int]) -> ET.Element:
    params = {**params, "tool": "journal-timelines", "email": EMAIL, "retmode": "xml"}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return ET.fromstring(response.read())


def search_pmids(query: str, limit: int) -> list[str]:
    payload = request_json("esearch.fcgi", {"db": "pubmed", "term": query, "retmax": limit})
    return payload.get("esearchresult", {}).get("idlist", [])


def chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index:index + size]


def parse_date_node(node: ET.Element | None) -> date | None:
    if node is None:
        return None
    year = node.findtext("Year")
    month = node.findtext("Month") or "1"
    day = node.findtext("Day") or "1"
    if not year:
        return None
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def best_publication_date(article: ET.Element) -> date | None:
    for status in ("epublish", "ppublish", "aheadofprint", "ecollection"):
        node = article.find(f".//PubMedPubDate[@PubStatus='{status}']")
        parsed = parse_date_node(node)
        if parsed:
            return parsed
    article_date = article.find(".//ArticleDate")
    parsed = parse_date_node(article_date)
    if parsed:
        return parsed
    pub_date = article.find(".//JournalIssue/PubDate")
    return parse_date_node(pub_date)


def parse_article(article: ET.Element) -> ArticleTiming | None:
    pmid = article.findtext(".//PMID")
    journal = article.findtext(".//Journal/Title")
    if not pmid or not journal:
        return None

    received = parse_date_node(article.find(".//PubMedPubDate[@PubStatus='received']"))
    accepted = parse_date_node(article.find(".//PubMedPubDate[@PubStatus='accepted']"))
    published = best_publication_date(article)
    issn = article.findtext(".//Journal/ISSN")

    return ArticleTiming(
        pmid=pmid,
        journal=journal,
        issn=issn,
        received=received,
        accepted=accepted,
        published=published,
    )


def fetch_articles(pmids: list[str]) -> list[ArticleTiming]:
    articles: list[ArticleTiming] = []
    for batch in chunks(pmids, 100):
        root = request_xml("efetch.fcgi", {"db": "pubmed", "id": ",".join(batch)})
        for node in root.findall(".//PubmedArticle"):
            article = parse_article(node)
            if article:
                articles.append(article)
        time.sleep(0.34)
    return articles


def median(values: list[int]) -> int | None:
    if not values:
        return None
    return round(statistics.median(values))


def aggregate(articles: list[ArticleTiming]) -> list[dict]:
    grouped: dict[str, list[ArticleTiming]] = defaultdict(list)
    for article in articles:
        grouped[article.journal].append(article)

    rows = []
    for journal, items in grouped.items():
        decision = [item.submission_to_acceptance for item in items if item.submission_to_acceptance is not None]
        production = [item.acceptance_to_publication for item in items if item.acceptance_to_publication is not None]
        total = [item.submission_to_publication for item in items if item.submission_to_publication is not None]
        full = [item for item in items if item.submission_to_publication is not None]
        rows.append({
            "journal": journal,
            "issn": next((item.issn for item in items if item.issn), None),
            "articles": len(items),
            "usableArticles": len(full),
            "coverage": round(len(full) / len(items), 3) if items else 0,
            "submissionToAcceptance": median(decision),
            "acceptanceToPublication": median(production),
            "submissionToPublication": median(total),
            "pmids": [item.pmid for item in items],
        })

    return sorted(rows, key=lambda row: (row["submissionToPublication"] is None, row["submissionToPublication"] or 999999))


def parse_pmids(raw: str) -> list[str]:
    return [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pmids", help="Comma or newline separated PMIDs")
    parser.add_argument("--query", help="PubMed search query")
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()

    if args.pmids:
        pmids = parse_pmids(args.pmids)
    elif args.query:
        pmids = search_pmids(args.query, args.limit)
    else:
        parser.error("Provide --pmids or --query")

    articles = fetch_articles(pmids)
    output = {
        "source": "PubMed E-utilities",
        "inputCount": len(pmids),
        "parsedCount": len(articles),
        "journals": aggregate(articles),
    }
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
