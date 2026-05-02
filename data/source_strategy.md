# Source Strategy

This project needs two different data layers.

## 1. Journal Registry Layer

This answers: is the journal indexed or ranked?

Fields:

- title
- publisher
- ISSN
- eISSN
- field
- Scopus status
- Web of Science status
- Web of Science index family, such as SCIE, SSCI, AHCI, ESCI
- ABDC rating, such as A*, A, B, C
- source file and retrieval date

Preferred sources:

- Scopus Source List exported from Scopus Sources.
- Web of Science Master Journal List / downloadable Core Collection lists.
- ABDC Journal Quality List, currently 2022 completed list while the 2025 review is underway.

## 2. Timeline Evidence Layer

This answers: how long does the journal usually take?

Fields:

- PMID or DOI
- received date
- accepted date
- electronic publication date
- print publication date
- journal title
- ISSN/eISSN
- evidence source

Timeline estimates should be shown only when there are enough records with full dates. If the registry says a journal exists but dates are unavailable, the UI should show `Unknown`, not an invented estimate.

## Import Workflow

1. Download/export the official list where licensing permits.
2. Convert it to CSV with the columns in `data/import_template.csv`.
3. Run:

   ```powershell
   python scripts/normalize_journals.py data/import_template.csv > data/journals.json
   ```

4. Review changes before publishing.
