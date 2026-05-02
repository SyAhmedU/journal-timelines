"""Harvest article-level lifecycle evidence from PubMed.

This is the ground-level data collector. It does not produce journal estimates
directly; it writes one row per article with received, accepted, and published
dates where PubMed has deposited them. Journal-level timelines are calculated by
scripts/aggregate_article_evidence.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from pathlib import Path


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "asrarsaa@gmail.com"
ROOT = Path(__file__).resolve().parents[1]


def request_json(path: str, params: dict[str, str | int]) -> dict:
    params = {**params, "tool": "journal-timelines", "email": EMAIL, "retmode": "json"}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=45) as response:
        return json.loads(response.read())


def request_xml(path: str, params: dict[str, str | int]) -> ET.Element:
    params = {**params, "tool": "journal-timelines", "email": EMAIL, "retmode": "xml"}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return ET.fromstring(response.read())


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


def doi(article: ET.Element) -> str:
    for node in article.findall(".//ArticleId"):
        if node.attrib.get("IdType") == "doi" and node.text:
            return node.text.strip()
    return ""


def clean_text(value: str | None) -> str:
    return " ".join((value or "").split())


def format_issn(value: str | None) -> str:
    text = "".join(ch for ch in (value or "") if ch.isalnum())
    if len(text) == 8:
        return f"{text[:4]}-{text[4:]}"
    return value or ""


def search_pmids_for_journal(journal: dict, max_articles: int, years: int) -> list[str]:
    terms = []
    for issn in [journal.get("issn"), journal.get("eissn")]:
        if issn:
            terms.append(f"{format_issn(issn)}[ISSN]")
    if not terms and journal.get("journal"):
        terms.append(f'"{journal["journal"]}"[Journal]')
    if not terms:
        return []
    end_year = datetime.now(UTC).year
    start_year = end_year - years
    query = f"({' OR '.join(terms)}) AND journal article[Publication Type] AND {start_year}:{end_year}[dp]"
    payload = request_json("esearch.fcgi", {
        "db": "pubmed",
        "term": query,
        "retmax": max_articles,
        "sort": "pub date",
    })
    return payload.get("esearchresult", {}).get("idlist", [])


def chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index:index + size]


def article_rows(pmids: list[str]) -> list[dict]:
    rows = []
    harvested_at = datetime.now(UTC).date().isoformat()
    for batch in chunks(pmids, 100):
        root = request_xml("efetch.fcgi", {"db": "pubmed", "id": ",".join(batch)})
        for article in root.findall(".//PubmedArticle"):
            pmid = article.findtext(".//PMID") or ""
            journal = clean_text(article.findtext(".//Journal/Title"))
            title = clean_text("".join(article.findtext(".//ArticleTitle") or ""))
            issn = clean_text(article.findtext(".//Journal/ISSN"))
            received = parse_date(article.find(".//PubMedPubDate[@PubStatus='received']"))
            accepted = parse_date(article.find(".//PubMedPubDate[@PubStatus='accepted']"))
            published = publication_date(article)
            review_days = (accepted - received).days if received and accepted and accepted >= received else None
            production_days = (published - accepted).days if accepted and published and published >= accepted else None
            total_days = (published - received).days if received and published and published >= received else None
            if total_days is None:
                continue
            rows.append({
                "source": "pubmed",
                "source_record_id": pmid,
                "doi": doi(article),
                "title": title,
                "journal": journal,
                "issn": issn,
                "eissn": "",
                "received_date": received.isoformat() if received else "",
                "accepted_date": accepted.isoformat() if accepted else "",
                "published_date": published.isoformat() if published else "",
                "review_days": review_days if review_days is not None else "",
                "production_days": production_days if production_days is not None else "",
                "total_days": total_days,
                "evidence_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "harvested_at": harvested_at,
            })
        time.sleep(0.34)
    return rows


def selected_journals(registry: list[dict], titles: set[str], limit: int) -> list[dict]:
    if titles:
        wanted = {title.lower() for title in titles}
        return [row for row in registry if (row.get("journal") or "").lower() in wanted]
    return [row for row in registry if row.get("issn") or row.get("eissn")][:limit]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--journal", action="append", default=[], help="Exact journal title; repeatable")
    parser.add_argument("--limit-journals", type=int, default=50)
    parser.add_argument("--articles-per-journal", type=int, default=120)
    parser.add_argument("--years", type=int, default=8)
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    journals = selected_journals(registry, set(args.journal), args.limit_journals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(csv.DictReader((ROOT / "data/article_evidence_template.csv").open(encoding="utf-8")).fieldnames or [])
    seen: set[str] = set()
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for journal in journals:
            pmids = search_pmids_for_journal(journal, args.articles_per_journal, args.years)
            time.sleep(0.34)
            for row in article_rows(pmids):
                key = row["source_record_id"] or row["doi"]
                if key and key not in seen:
                    seen.add(key)
                    writer.writerow(row)


if __name__ == "__main__":
    main()
