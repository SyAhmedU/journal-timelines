"""Normalize journal registry CSV files into JSON.

Expected columns are shown in data/import_template.csv. This script intentionally
uses CSV as the interchange format because Scopus, Web of Science, and ABDC
exports may arrive as Excel files that can be converted outside the app.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "scopus", "wos"}


def clean(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def split_indexes(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.replace(",", "|").split("|") if part.strip()]


def key_for(row: dict[str, str]) -> str:
    issn = clean(row.get("issn")) or clean(row.get("eissn"))
    if issn:
        return issn.lower()
    return (clean(row.get("title")) or "").lower()


def merge(existing: dict, row: dict[str, str]) -> dict:
    existing["journal"] = existing.get("journal") or clean(row.get("title"))
    existing["publisher"] = existing.get("publisher") or clean(row.get("publisher"))
    existing["issn"] = existing.get("issn") or clean(row.get("issn"))
    existing["eissn"] = existing.get("eissn") or clean(row.get("eissn"))
    existing["field"] = existing.get("field") or clean(row.get("field")) or "unknown"
    existing["scopus"] = existing.get("scopus", False) or truthy(row.get("scopus"))
    existing["wos"] = existing.get("wos", False) or truthy(row.get("wos"))
    existing["wosIndexes"] = sorted(set(existing.get("wosIndexes", []) + split_indexes(row.get("wos_indexes"))))
    existing["abdcRating"] = existing.get("abdcRating") or clean(row.get("abdc_rating"))
    existing.setdefault("articles", 0)
    existing.setdefault("coverage", 0)
    existing.setdefault("submissionToAcceptance", None)
    existing.setdefault("acceptanceToPublication", None)
    existing.setdefault("submissionToPublication", None)
    existing.setdefault("sources", [])
    source = clean(row.get("source"))
    if source and source not in existing["sources"]:
        existing["sources"].append(source)
    return existing


def normalize(paths: list[Path]) -> list[dict]:
    journals: dict[str, dict] = {}
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                key = key_for(row)
                if not key:
                    continue
                journals[key] = merge(journals.get(key, {}), row)
    return sorted(journals.values(), key=lambda item: (item.get("journal") or "").lower())


def main() -> None:
    paths = [Path(arg) for arg in sys.argv[1:]]
    if not paths:
        raise SystemExit("Usage: python scripts/normalize_journals.py data/list.csv [data/list2.csv]")
    print(json.dumps(normalize(paths), indent=2))


if __name__ == "__main__":
    main()
