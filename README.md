# Journal Timelines

Project 5: a tool for choosing journals by index coverage, ranking, and estimated publication timeline.

## Problem

Researchers often choose journals without knowing the likely time cost. Publisher pages may advertise review speed, but the comparable evidence is scattered across article metadata and is not always deposited.

## MVP Scope

The first practical version has two layers:

1. A journal registry for Scopus, Web of Science, and ABDC journals.
2. A timeline evidence layer that estimates publication speed only where article lifecycle dates exist.

PubMed-indexed records are useful for timeline estimation because they can include article lifecycle dates such as:

- received
- accepted
- electronic publication
- print publication

The timeline layer computes journal-level medians:

- submission to acceptance
- acceptance to publication
- submission to publication
- coverage rate: how many records include enough dates to calculate a reliable timeline

## Files

- `index.html` - static dashboard prototype with demo data
- `fetch_pubmed.py` - PubMed data fetcher and parser
- `scripts/normalize_journals.py` - CSV normalizer for official journal lists
- `data/import_template.csv` - registry import format
- `data/source_strategy.md` - long-term source plan
- `README.md` - project notes and data assumptions

## Data Caveat

This project should not fake precision. If a journal or publisher does not deposit received/accepted/publication dates, the app should show low coverage or no estimate.

Scopus and Web of Science registry coverage should be imported from official exports where the user has access. ABDC should use the official Journal Quality List release; the completed list currently available from ABDC is 2022, while ABDC has a 2025 review process underway.

## Next Build Steps

1. Import official Scopus Source List export.
2. Import official Web of Science Master Journal List/Core Collection exports.
3. Import official ABDC Journal Quality List.
4. Match journals by ISSN/eISSN, then title fallback.
5. Search PubMed/Crossref/publisher metadata for lifecycle dates.
6. Aggregate timing samples by journal and display confidence.
