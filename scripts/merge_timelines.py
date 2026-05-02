"""Merge journal registry JSON with timeline evidence CSV.

The registry is keyed by ISSN/eISSN where possible. Timeline evidence should be
derived from article-level lifecycle dates and aggregated before merge.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def norm_issn(value: str | None) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def number(value: str | None, integer: bool = True):
    if value is None or value == "":
        return None
    return int(float(value)) if integer else float(value)


def keys_for(row: dict) -> set[str]:
    keys = {norm_issn(row.get("issn")), norm_issn(row.get("eissn"))}
    return {key for key in keys if key}


def load_timelines(path: Path) -> dict[str, dict]:
    evidence: dict[str, dict] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            item = {
                "articles": number(row.get("articles")) or 0,
                "coverage": number(row.get("coverage"), integer=False) or 0,
                "submissionToAcceptance": number(row.get("submission_to_acceptance")),
                "acceptanceToPublication": number(row.get("acceptance_to_publication")),
                "submissionToPublication": number(row.get("submission_to_publication")),
                "totalP25": number(row.get("total_p25")),
                "totalP75": number(row.get("total_p75")),
                "timelineConfidence": row.get("confidence") or "",
                "timelineSource": row.get("source") or "unknown",
                "timelineNote": row.get("note") or "",
            }
            for key in keys_for(row):
                evidence[key] = item
    return evidence


def merge(registry_path: Path, timeline_path: Path) -> list[dict]:
    rows = json.loads(registry_path.read_text(encoding="utf-8"))
    evidence = load_timelines(timeline_path)
    for row in rows:
        for key in keys_for(row):
            if key in evidence:
                row.update(evidence[key])
                break
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("timelines", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    rows = merge(args.registry, args.timelines)
    content = json.dumps(rows, indent=2 if args.pretty else None, separators=None if args.pretty else (",", ":"))
    args.output.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
