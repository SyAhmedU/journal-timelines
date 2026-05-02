"""Aggregate article-level evidence into journal-level timeline medians."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def norm_issn(value: str | None) -> str:
    return "".join(ch for ch in (value or "").lower() if ch.isalnum())


def as_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def percentile(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * q)
    return ordered[index]


def median(values: list[int]) -> int | None:
    return round(statistics.median(values)) if values else None


def confidence(sample_size: int, coverage: float) -> str:
    if sample_size >= 50 and coverage >= 0.5:
        return "high"
    if sample_size >= 20 and coverage >= 0.25:
        return "medium"
    return "low"


def aggregate(input_path: Path) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = norm_issn(row.get("issn")) or (row.get("journal") or "").strip().lower()
            if key:
                groups[key].append(row)

    output = []
    for rows in groups.values():
        totals = [as_int(row.get("total_days")) for row in rows if as_int(row.get("total_days")) is not None]
        reviews = [as_int(row.get("review_days")) for row in rows if as_int(row.get("review_days")) is not None]
        productions = [as_int(row.get("production_days")) for row in rows if as_int(row.get("production_days")) is not None]
        if not totals:
            continue
        sample_size = len(rows)
        coverage = len(totals) / sample_size if sample_size else 0
        first = rows[0]
        output.append({
            "title": first.get("journal"),
            "issn": first.get("issn"),
            "eissn": first.get("eissn"),
            "articles": sample_size,
            "coverage": round(coverage, 3),
            "submission_to_acceptance": median(reviews),
            "acceptance_to_publication": median(productions),
            "submission_to_publication": median(totals),
            "total_p25": percentile(totals, 0.25),
            "total_p75": percentile(totals, 0.75),
            "confidence": confidence(len(totals), coverage),
            "source": "article_evidence",
            "note": "Aggregated from article-level lifecycle dates.",
        })
    return sorted(output, key=lambda row: (row["submission_to_publication"] or 999999, row["title"] or ""))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    rows = aggregate(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "title", "issn", "eissn", "articles", "coverage",
            "submission_to_acceptance", "acceptance_to_publication",
            "submission_to_publication", "total_p25", "total_p75",
            "confidence", "source", "note",
        ])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
