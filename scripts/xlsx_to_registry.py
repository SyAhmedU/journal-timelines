"""Convert Scopus/registry XLSX exports to Journal Timelines CSV.

This parser uses only the Python standard library so the project can ingest
official Excel exports without adding a build system.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def column_index(cell_ref: str) -> int:
    letters = re.match(r"[A-Z]+", cell_ref).group(0)
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def shared_strings(book: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(book.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    values = []
    for item in root.findall("main:si", NS):
        parts = [node.text or "" for node in item.findall(".//main:t", NS)]
        values.append("".join(parts))
    return values


def first_sheet_path(book: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(book.read("xl/workbook.xml"))
    first = workbook.find("main:sheets/main:sheet", NS)
    if first is None:
        raise ValueError("Workbook has no sheets")
    rel_id = first.attrib[f"{{{NS['rel']}}}id"]

    rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
    for rel in rels.findall("pkgrel:Relationship", NS):
        if rel.attrib["Id"] == rel_id:
            target = rel.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else f"xl/{target}"
    raise ValueError("Could not resolve first worksheet")


def cell_text(cell: ET.Element, strings: list[str]) -> str:
    value = cell.findtext("main:v", default="", namespaces=NS)
    if cell.attrib.get("t") == "s" and value:
        return strings[int(value)]
    if cell.attrib.get("t") == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", NS))
    return value


def iter_rows(path: Path):
    with zipfile.ZipFile(path) as book:
        strings = shared_strings(book)
        sheet_path = first_sheet_path(book)
        root = ET.fromstring(book.read(sheet_path))
        for row in root.findall(".//main:sheetData/main:row", NS):
            values: list[str] = []
            for cell in row.findall("main:c", NS):
                ref = cell.attrib.get("r", "A1")
                idx = column_index(ref)
                while len(values) <= idx:
                    values.append("")
                values[idx] = cell_text(cell, strings).strip()
            yield values


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def pick(row: dict[str, str], *names: str) -> str:
    for name in names:
        value = row.get(name)
        if value:
            return value
    return ""


def convert_scopus(input_path: Path, output_path: Path) -> int:
    rows = iter_rows(input_path)
    headers = [normalize_header(value) for value in next(rows)]
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source", "title", "publisher", "issn", "eissn", "field", "scopus", "wos", "wos_indexes", "abdc_rating"],
        )
        writer.writeheader()
        for values in rows:
            if not any(values):
                continue
            row = {headers[i]: values[i] if i < len(values) else "" for i in range(len(headers))}
            title = pick(row, "source_title", "title", "sourcetitle")
            if not title:
                continue
            source_type = pick(row, "source_type", "type").lower()
            if source_type and "journal" not in source_type:
                continue
            issn = pick(row, "print_issn", "issn", "p_issn")
            eissn = pick(row, "e_issn", "eissn", "electronic_issn")
            field = pick(row, "all_science_journal_classification_codes_asjc", "asjc", "subject_area")
            writer.writerow({
                "source": "scopus_mar_2026",
                "title": title,
                "publisher": pick(row, "publisher_s_name", "publisher", "publisher_name"),
                "issn": issn,
                "eissn": eissn,
                "field": field or "unknown",
                "scopus": "true",
                "wos": "",
                "wos_indexes": "",
                "abdc_rating": "",
            })
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--kind", choices=["scopus"], default="scopus")
    args = parser.parse_args()

    if args.kind == "scopus":
        count = convert_scopus(args.input, args.output)
    else:
        raise AssertionError(args.kind)
    print(f"Wrote {count} rows to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
