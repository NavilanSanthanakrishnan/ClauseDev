# Step2

Step2 is the law-database layer for contradiction analysis.

Current goal:

- turn the local `CaliforniaCodeData` scrape into a clean SQL database
- treat the local JSON only as a table of contents, not as trusted law text
- fetch official California law text from `leginfo.legislature.ca.gov`
- parse sections into normalized tables that are usable for later contradiction search

## What The Input Actually Is

The local `CaliforniaCodeData` folder is not a clean laws database.

What it contains:

- one directory per California code
- one JSON file per scraped division/title
- inside each JSON:
  - `division_name`
  - `url`
  - `articles`

The `articles` map points to official California Legislature URLs. The per-file `url` also matters, because many divisions only expose law text through that branch page.

The builder therefore treats both of these as source references:

- the file-level `division_url`
- every URL in the `articles` map

## Database Output

The Step2 pipeline currently has two storage layers:

- SQLite as the local crawl/scrape staging DB
- PostgreSQL as the browseable app-facing DB
- official California `PUBINFO` bulk data as the completion path for full code text

The schema contains:

- `code_books`
- `toc_files`
- `article_refs`
- `source_pages`
- `sections`
- `section_sources`
- `section_collisions`
- `section_fts`

This is designed so later AI workflows can:

- search by code and section number
- full-text search California sections
- trace every section back to official page sources
- detect duplicates or conflicting section text during ingest

## Setup

```bash
cd /Users/navilan/Documents/Clause/Step2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Build Metadata Only

This loads the local TOC JSON into SQLite without fetching official pages yet.

```bash
source .venv/bin/activate
python scripts/build_california_code_db.py --metadata-only --rebuild
```

## Build A Pilot Code

This is the recommended first validation run.

```bash
source .venv/bin/activate
python scripts/build_california_code_db.py --only-code WIC --workers 2 --rebuild
```

If `leginfo` starts rate limiting with `403`, use the batch runner instead:

```bash
source .venv/bin/activate
python scripts/run_california_code_batches.py --only-code WIC --batch-size 25 --workers 1 --sleep-seconds 20 --rebuild
```

## Build More Of California

```bash
source .venv/bin/activate
python scripts/build_california_code_db.py --workers 2 --rebuild
```

For the full California crawl, the batch runner is safer:

```bash
source .venv/bin/activate
python scripts/run_california_code_batches.py --batch-size 25 --workers 1 --sleep-seconds 20 --rebuild
```

You can also cap a run:

```bash
source .venv/bin/activate
python scripts/build_california_code_db.py --limit-pages 500 --workers 2 --rebuild
```

## Output

Default SQLite staging path:

- `Step2/data/california_code.db`

The database file and the raw local `CaliforniaCodeData` folder are intentionally gitignored.

## Sync To PostgreSQL

Create the PostgreSQL database once:

```bash
/opt/homebrew/opt/postgresql@17/bin/createdb -h 127.0.0.1 -p 55432 california_code
```

Then sync the current Step2 data into PostgreSQL:

```bash
source .venv/bin/activate
python scripts/sync_california_code_to_postgres.py --truncate
```

Default PostgreSQL connection:

- host: `127.0.0.1`
- port: `55432`
- database: `california_code`
- user: `navilan`
- password: blank

In TablePlus, this is a `PostgreSQL` connection.

Open these first:

- `section_search`
- `sections`
- `source_pages`
- `code_books`

## Official Bulk Load

For a complete California code corpus, use the official Legislature bulk feed instead of page crawling.

Download the archive:

```bash
cd /Users/navilan/Documents/Clause/Step2/cache
curl -L -o pubinfo_2025.zip https://downloads.leginfo.legislature.ca.gov/pubinfo_2025.zip
```

Load it into PostgreSQL:

```bash
cd /Users/navilan/Documents/Clause/Step2
source .venv/bin/activate
python scripts/load_official_california_codes.py --truncate
```

This creates:

- `official_codes`
- `official_law_toc`
- `official_law_toc_sections`
- `official_law_sections`
- `law_section_search`
- `section_search`
- `law_section_embedding_input`

Main browse/query views after the official load:

- `section_search`: complete section-level browse/search view
- `law_section_search`: richer official hierarchy view
- `law_section_embedding_input`: semantic-ready text projection for later embeddings or reranking

## U.S. Code

Federal U.S. Code assets now live under:

- `Step2/uscode/`

That directory contains:

- `uscode_local.db`
- `xml_uscAll_current.zip`
- PostgreSQL schema SQL
- import/query/build scripts

Expected PostgreSQL target for federal law:

- database: `uscode_local`

`source_pages.fetch_status` will distinguish between:

- `parsed`
- `parsed_empty`
- `failed`
- `skipped_non_text`

## Why This Structure

The later contradiction-analysis step needs clean section-level law text, not just URLs or broad division names.

This database is structured around deduplicated sections so the next stages can:

- retrieve potentially conflicting sections
- compare bill obligations against existing law
- separate state-level contradictions from federal contradictions
- cite the exact California section text and official source URL
