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
- `data/journals.json` - generated journal registry consumed by the dashboard
- `data/scopus_registry.csv` - normalized Scopus source title list
- `data/source_manifest.json` - source provenance and pending sources
- `fetch_pubmed.py` - PubMed data fetcher and parser
- `scripts/normalize_journals.py` - CSV normalizer for official journal lists
- `scripts/xlsx_to_registry.py` - standard-library XLSX converter for registry exports
- `data/import_template.csv` - registry import format
- `data/source_strategy.md` - long-term source plan
- `README.md` - project notes and data assumptions

## Data Caveat

This project should not fake precision. If a journal or publisher does not deposit received/accepted/publication dates, the app should show low coverage or no estimate.

The current generated registry includes the official Elsevier Scopus Source title list for March 2026. Web of Science collection downloads require a free Master Journal List login. ABDC should use the official Journal Quality List release; the completed list currently available from ABDC is 2022, while ABDC has a 2025 review process underway.

Scopus and Web of Science title lists do not include manuscript lifecycle dates. Publication timeline estimates must be harvested separately from article metadata, then joined back to journals by ISSN/eISSN/title.

## Next Build Steps

1. Import Web of Science Master Journal List/Core Collection exports after login.
2. Import official ABDC Journal Quality List.
3. Match journals by ISSN/eISSN, then title fallback.
4. Search PubMed/Crossref/publisher metadata for lifecycle dates.
5. Aggregate timing samples by journal and display confidence.
6. Add background refresh jobs for monthly Scopus/WoS list updates.
