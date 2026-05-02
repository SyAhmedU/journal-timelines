# Journal Timelines

Project 5: a tool for estimating how long journals take from manuscript submission to publication.

## Problem

Researchers often choose journals without knowing the likely time cost. Publisher pages may advertise review speed, but the comparable evidence is scattered across article metadata and is not always deposited.

## MVP Scope

The first practical version focuses on PubMed-indexed journals because PubMed records can include article lifecycle dates such as:

- received
- accepted
- electronic publication
- print publication

The MVP computes journal-level medians:

- submission to acceptance
- acceptance to publication
- submission to publication
- coverage rate: how many records include enough dates to calculate a reliable timeline

## Files

- `index.html` - static dashboard prototype with demo data
- `fetch_pubmed.py` - PubMed data fetcher and parser
- `README.md` - project notes and data assumptions

## Data Caveat

This project should not fake precision. If a journal or publisher does not deposit received/accepted/publication dates, the app should show low coverage or no estimate.

## Next Build Steps

1. Search PubMed by journal ISSN/title and recent publication year.
2. Fetch article XML with E-utilities.
3. Parse lifecycle dates by PMID.
4. Aggregate by journal.
5. Export `journals.json` for the web dashboard.
