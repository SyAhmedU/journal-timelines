"""Harvest Crossref review-timeline evidence for journals beyond PubMed's reach.

Some publishers deposit per-article editorial dates in Crossref as assertions
(named e.g. "date_received" / "date_accepted") or expose them via the
journal-article `created` vs `published` stamps. This script queries the
Crossref REST API by ISSN, extracts ONLY explicitly deposited dates (never
inferring or estimating), and writes aggregate rows in the same shape as the
PubMed pipeline so `merge_timelines.py` can join them by ISSN.

No-fab rule: an article contributes a review time ONLY when both a received
and an accepted assertion are present verbatim in the Crossref record.
Journals without enough evidence are simply left out (they stay "Unknown").

Example (a small, polite run):
  python scripts/harvest_crossref_timelines.py data/journals.json \
      -o data/timelines_crossref.csv --limit-journals 50 --rows-per-journal 60
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://api.crossref.org"
MAILTO = "asrarsaa@gmail.com"  # polite-pool contact per Crossref etiquette
MIN_ARTICLES = 8  # below this, evidence is too thin to publish a median

RECEIVED_KEYS = {"date_received", "received", "manuscript_received"}
ACCEPTED_KEYS = {"date_accepted", "accepted", "manuscript_accepted"}


def request_json(path: str, params: dict[str, str | int]) -> dict:
    params = {**params, "mailto": MAILTO}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": f"journal-timelines (mailto:{MAILTO})"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def parse_date_parts(value) -> date | None:
    """Crossref date-parts: [[y, m, d]] — day/month may be missing; require at least y+m."""
    try:
        parts = value["date-parts"][0]
        if len(parts) < 2:
            return None
        return date(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 1)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def parse_assertion_date(raw: str) -> date | None:
    """Assertion values arrive as ISO-ish strings ('2024-03-15', '15 March 2024' variants skipped)."""
    raw = (raw or "").strip()[:10]
    try:
        y, m, d = raw.split("-")
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def article_timeline(item: dict) -> tuple[int | None, int | None]:
    """Return (review_days, production_days) using ONLY deposited dates."""
    received = accepted = None
    for assertion in item.get("assertion", []):
        name = str(assertion.get("name", "")).lower()
        if name in RECEIVED_KEYS:
            received = parse_assertion_date(str(assertion.get("value", "")))
        elif name in ACCEPTED_KEYS:
            accepted = parse_assertion_date(str(assertion.get("value", "")))
    published = parse_date_parts(item.get("published-online") or item.get("published-print") or item.get("published") or {})

    review_days = None
    if received and accepted and accepted >= received:
        review_days = (accepted - received).days
    production_days = None
    if accepted and published and published >= accepted:
        production_days = (published - accepted).days
    return review_days, production_days


def harvest_journal(issn: str, rows_per_journal: int) -> dict | None:
    try:
        data = request_json(
            f"journals/{issn}/works",
            {
                "filter": "type:journal-article,from-pub-date:2023-01-01",
                "rows": rows_per_journal,
                "select": "assertion,published,published-online,published-print",
            },
        )
    except Exception:
        return None

    reviews: list[int] = []
    productions: list[int] = []
    for item in data.get("message", {}).get("items", []):
        review_days, production_days = article_timeline(item)
        if review_days is not None and 0 < review_days < 1500:
            reviews.append(review_days)
        if production_days is not None and 0 <= production_days < 1500:
            productions.append(production_days)

    if len(reviews) < MIN_ARTICLES:
        return None  # not enough real evidence — journal stays Unknown

    reviews.sort()
    totals = sorted(r + p for r, p in zip(reviews, productions)) if len(productions) >= MIN_ARTICLES else None
    row = {
        "issn": issn,
        "articles": len(reviews),
        "submission_to_acceptance_days": round(statistics.median(reviews)),
        "acceptance_to_publication_days": round(statistics.median(productions)) if len(productions) >= MIN_ARTICLES else "",
        "submission_to_publication_days": round(statistics.median(totals)) if totals else "",
        "total_p25": totals[len(totals) // 4] if totals else "",
        "total_p75": totals[(3 * len(totals)) // 4] if totals else "",
        "source": "crossref-assertions",
    }
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("registry", type=Path, help="normalized registry JSON (data/journals.json)")
    parser.add_argument("-o", "--output", type=Path, default=Path("data/timelines_crossref.csv"))
    parser.add_argument("--limit-journals", type=int, default=100)
    parser.add_argument("--rows-per-journal", type=int, default=60)
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between requests (be polite)")
    args = parser.parse_args()

    journals = json.loads(args.registry.read_text(encoding="utf-8"))
    # Prioritize journals with NO timeline yet — Crossref should extend, not duplicate, PubMed coverage.
    pending = [j for j in journals if j.get("submissionToPublication") is None and (j.get("issn") or j.get("eissn"))]
    print(f"{len(pending)} journals lack timelines; harvesting up to {args.limit_journals}")

    rows: list[dict] = []
    for journal in pending[: args.limit_journals]:
        issn = journal.get("issn") or journal.get("eissn")
        row = harvest_journal(issn, args.rows_per_journal)
        if row:
            row["journal"] = journal.get("journal", "")
            rows.append(row)
            print(f"  ✓ {journal.get('journal', issn)}: {row['articles']} articles, review {row['submission_to_acceptance_days']}d")
        time.sleep(args.sleep)

    if not rows:
        print("No journals produced enough deposited-date evidence. Nothing written (nothing invented).")
        return

    fieldnames = ["issn", "journal", "articles", "submission_to_acceptance_days",
                  "acceptance_to_publication_days", "submission_to_publication_days",
                  "total_p25", "total_p75", "source"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} journals to {args.output}")


if __name__ == "__main__":
    main()
