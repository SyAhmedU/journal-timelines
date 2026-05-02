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
- `data/article_evidence_template.csv` - article-level evidence schema
- `data/article_evidence_pubmed_sample.csv` - harvested article-level PubMed evidence sample
- `data/timelines_pubmed_sample.csv` - journal-level medians/ranges aggregated from article rows
- `data/source_manifest.json` - source provenance and pending sources
- `fetch_pubmed.py` - PubMed data fetcher and parser
- `scripts/normalize_journals.py` - CSV normalizer for official journal lists
- `scripts/xlsx_to_registry.py` - standard-library XLSX converter for registry exports
- `scripts/merge_timelines.py` - joins timeline evidence into the registry by ISSN/eISSN
- `scripts/harvest_pubmed_timelines.py` - batch PubMed lifecycle-date harvester for journals with ISSN/eISSN
- `scripts/harvest_pubmed_articles.py` - article-level PubMed lifecycle-date harvester
- `scripts/aggregate_article_evidence.py` - aggregates raw article evidence into journal timelines
- `data/import_template.csv` - registry import format
- `data/source_strategy.md` - long-term source plan
- `README.md` - project notes and data assumptions

## Data Caveat

This project should not fake precision. If a journal or publisher does not deposit received/accepted/publication dates, the app should show low coverage or no estimate.

The current generated registry includes the official Elsevier Scopus Source title list for March 2026. Web of Science collection downloads require a free Master Journal List login. ABDC should use the official Journal Quality List release; the completed list currently available from ABDC is 2022, while ABDC has a 2025 review process underway.

Scopus and Web of Science title lists do not include manuscript lifecycle dates. Publication timeline estimates are harvested separately from article metadata, aggregated from article rows, then joined back to journals by ISSN/eISSN/title.

## Current Product Features

- Search by title, publisher, ISSN/eISSN, and subject.
- Filter by Scopus, Web of Science, ABDC, field, ABDC rating, known timeline status, maximum total days, and minimum evidence articles.
- Sort by fastest total publication, fastest review decision, fastest production, strongest evidence, or title.
- Copy a shareable master link that preserves the current filters.
- Export current filtered results to CSV.

## Next Build Steps

1. Import Web of Science Master Journal List/Core Collection exports after login.
2. Import official ABDC Journal Quality List.
3. Match journals by ISSN/eISSN, then title fallback.
4. Search PubMed/Crossref/publisher metadata for lifecycle dates.
5. Aggregate timing samples by journal and display confidence.
6. Add background refresh jobs for monthly Scopus/WoS list updates.

## Rebuild Data

```powershell
python scripts\normalize_journals.py data\scopus_registry.csv -o data\journals_registry.json
python scripts\aggregate_article_evidence.py data\article_evidence_pubmed_sample.csv -o data\timelines_pubmed_sample.csv
python scripts\merge_timelines.py data\journals_registry.json data\timelines_pubmed_sample.csv -o data\journals.json
```

To grow the timeline evidence from PubMed:

```powershell
python scripts\harvest_pubmed_articles.py data\journals_registry.json -o data\article_evidence_pubmed.csv --limit-journals 100 --articles-per-journal 120 --years 8
python scripts\aggregate_article_evidence.py data\article_evidence_pubmed.csv -o data\timelines_pubmed.csv
python scripts\merge_timelines.py data\journals_registry.json data\timelines_pubmed.csv -o data\journals.json
```
