"""Merge ABDC Journal Quality List ratings into the registry by ISSN.

The ABDC list is a free download (abdc.edu.au/abdc-journal-quality-list) but is
not redistributable here, so this script expects you to place the official
export at data/raw/abdc_jql.csv first (export the xlsx to CSV, or pass --xlsx
with openpyxl installed). Ratings are joined ONLY by exact normalized ISSN
match — no fuzzy title matching, so no wrong-journal ratings.

Usage:
  python scripts/ingest_abdc.py data/journals.json data/raw/abdc_jql.csv
  python scripts/ingest_abdc.py data/journals.json data/raw/abdc_jql.xlsx --xlsx
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

VALID_RATINGS = {"A*", "A", "B", "C"}


def norm_issn(value: str) -> str:
    return re.sub(r"[^0-9Xx]", "", str(value or "")).upper()


def read_abdc_csv(path: Path) -> dict[str, str]:
    """Map normalized ISSN -> rating. Column names vary across ABDC releases,
    so detect them by header keywords rather than position."""
    ratings: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if not header:
            sys.exit("ABDC file appears empty.")
        low = [str(h).strip().lower() for h in header]
        issn_cols = [i for i, h in enumerate(low) if "issn" in h]
        rating_cols = [i for i, h in enumerate(low) if "rating" in h or h in {"2022 rating", "abdc rating"}]
        if not issn_cols or not rating_cols:
            sys.exit(f"Couldn't find ISSN/rating columns in header: {header}")
        rating_col = rating_cols[0]
        for row in reader:
            if len(row) <= rating_col:
                continue
            rating = str(row[rating_col]).strip().upper().replace("A STAR", "A*")
            if rating not in VALID_RATINGS:
                continue
            for col in issn_cols:
                if len(row) > col:
                    issn = norm_issn(row[col])
                    if len(issn) == 8:
                        ratings[issn] = rating
    return ratings


def read_abdc_xlsx(path: Path) -> dict[str, str]:
    try:
        import openpyxl  # noqa: PLC0415 — optional dependency, only for --xlsx
    except ImportError:
        sys.exit("openpyxl not installed — export the ABDC xlsx to CSV instead.")
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = next(rows, None)
    if not header:
        sys.exit("ABDC workbook appears empty.")
    low = [str(h or "").strip().lower() for h in header]
    issn_cols = [i for i, h in enumerate(low) if "issn" in h]
    rating_cols = [i for i, h in enumerate(low) if "rating" in h]
    if not issn_cols or not rating_cols:
        sys.exit(f"Couldn't find ISSN/rating columns in header: {header}")
    ratings: dict[str, str] = {}
    for row in rows:
        rating = str(row[rating_cols[0]] or "").strip().upper().replace("A STAR", "A*")
        if rating not in VALID_RATINGS:
            continue
        for col in issn_cols:
            issn = norm_issn(row[col] if col < len(row) else "")
            if len(issn) == 8:
                ratings[issn] = rating
    return ratings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("registry", type=Path)
    parser.add_argument("abdc_file", type=Path)
    parser.add_argument("--xlsx", action="store_true", help="read the ABDC file as xlsx (needs openpyxl)")
    parser.add_argument("-o", "--output", type=Path, help="output path (defaults to overwriting the registry)")
    args = parser.parse_args()

    if not args.abdc_file.exists():
        sys.exit(f"ABDC file not found: {args.abdc_file}\nDownload the official list from abdc.edu.au first.")

    ratings = (read_abdc_xlsx if args.xlsx else read_abdc_csv)(args.abdc_file)
    print(f"Loaded {len(ratings)} rated journals from the ABDC list")

    journals = json.loads(args.registry.read_text(encoding="utf-8"))
    matched = 0
    for journal in journals:
        for key in ("issn", "eissn"):
            issn = norm_issn(journal.get(key, ""))
            if issn in ratings:
                journal["abdcRating"] = ratings[issn]
                matched += 1
                break

    output = args.output or args.registry
    output.write_text(json.dumps(journals, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Matched {matched} registry journals by exact ISSN; wrote {output}")
    print(f"({len(ratings) - matched} ABDC entries had no ISSN match — left untouched, never fuzzy-matched.)")


if __name__ == "__main__":
    main()
