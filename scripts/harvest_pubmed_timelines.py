"""Harvest PubMed lifecycle-date evidence for journals.

This script reads the normalized registry JSON, searches PubMed by ISSN/eISSN,
fetches recent article XML, and writes aggregate timeline rows compatible with
data/timelines_seed.csv.

Example:
  python scripts/harvest_pubmed_timelines.py data/journals.json -o data/timelines_pubmed.csv --limit-journals 100 --articles-per-journal 80
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "asrarsaa@gmail.com"


def request_xml(path: str, params: dict[str, str | int]) -> ET.Element:
    params = {**params, "tool": "journal-timelines", "email": EMAIL}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return ET.fromstring(response.read())


def request_json(path: str, params: dict[str, str | int]) -> dict:
    params = {**params, "tool": "journal-timelines", "email": EMAIL, "retmode": "json"}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read())


def parse_date(node: ET.Element | None) -> date | None:
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


def publication_date(article: ET.Element) -> date | None:
    for status in ("epublish", "ppublish", "aheadofprint", "ecollection"):
        parsed = parse_date(article.find(f".//PubMedPubDate[@PubStatus='{status}']"))
        if parsed:
            return parsed
    return parse_date(article.find(".//ArticleDate")) or parse_date(article.find(".//JournalIssue/PubDate"))


def search_pmids(issn: str, max_articles: int, years: int) -> list[str]:
    term = f'{issn}[ISSN] AND journal article[Publication Type] AND "last {years} years"[dp]'
    payload = request_json("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": max_articles, "sort": "pub date"})
    return payload.get("esearchresult", {}).get("idlist", [])


def fetch_batch(pmids: list[str]) -> list[tuple[int | None, int | None, int | None]]:
    if not pmids:
        return []
    root = request_xml("efetch.fcgi", {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"})
    rows = []
    for article in root.findall(".//PubmedArticle"):
        received = parse_date(article.find(".//PubMedPubDate[@PubStatus='received']"))
        accepted = parse_date(article.find(".//PubMedPubDate[@PubStatus='accepted']"))
        published = publication_date(article)
        review = (accepted - received).days if received and accepted and accepted >= received else None
        production = (published - accepted).days if accepted and published and published >= accepted else None
        total = (published - received).days if received and published and published >= received else None
        rows.append((review, production, total))
    return rows


def med(values: list[int]) -> int | None:
    return round(statistics.median(values)) if values else None


def harvest_journal(journal: dict, articles_per_journal: int, years: int) -> dict | None:
    issns = [journal.get("issn"), journal.get("eissn")]
    pmids: list[str] = []
    for issn in [value for value in issns if value]:
        pmids.extend(search_pmids(issn, articles_per_journal, years))
        time.sleep(0.34)
    pmids = list(dict.fromkeys(pmids))[:articles_per_journal]
    evidence = fetch_batch(pmids)
    full = [row for row in evidence if row[2] is not None]
    if not full:
        return None
    return {
        "title": journal.get("journal"),
        "issn": journal.get("issn"),
        "eissn": journal.get("eissn"),
        "articles": len(evidence),
        "coverage": round(len(full) / len(evidence), 3) if evidence else 0,
        "submission_to_acceptance": med([row[0] for row in evidence if row[0] is not None]),
        "acceptance_to_publication": med([row[1] for row in evidence if row[1] is not None]),
        "submission_to_publication": med([row[2] for row in evidence if row[2] is not None]),
        "source": "pubmed_harvest",
        "note": f"Harvested from PubMed last {years} years by ISSN/eISSN.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--limit-journals", type=int, default=100)
    parser.add_argument("--articles-per-journal", type=int, default=80)
    parser.add_argument("--years", type=int, default=5)
    args = parser.parse_args()

    journals = json.loads(args.registry.read_text(encoding="utf-8"))
    candidates = [row for row in journals if row.get("issn") or row.get("eissn")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
      writer = csv.DictWriter(handle, fieldnames=[
          "title", "issn", "eissn", "articles", "coverage",
          "submission_to_acceptance", "acceptance_to_publication",
          "submission_to_publication", "source", "note",
      ])
      writer.writeheader()
      for journal in candidates[:args.limit_journals]:
          row = harvest_journal(journal, args.articles_per_journal, args.years)
          if row:
              writer.writerow(row)


if __name__ == "__main__":
    main()
