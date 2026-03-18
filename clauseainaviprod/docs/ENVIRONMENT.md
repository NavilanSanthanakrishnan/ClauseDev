# Environment

`Clause` reads runtime configuration from an external file:

`/Users/navilan/Documents/ClauseAIProd/.env.clauseainaviprod`

That keeps secrets outside the project folders and outside Git.

## Active Gemini configuration

```bash
CLAUSE_GEMINI_API_KEY=...
CLAUSE_GEMINI_MODEL=gemini-2.5-flash
CLAUSE_GEMINI_EMBEDDING_MODEL=gemini-embedding-001
```

## Optional external law databases

```bash
CLAUSE_CALIFORNIA_CODE_DSN="dbname=california_code host=/Users/navilan/Documents/openstates-data-2026/pg-runtime port=55432"
CLAUSE_USCODE_DSN="dbname=uscode_local host=/Users/navilan/Documents/openstates-data-2026/pg-runtime port=55432"
```

## Optional

```bash
CLAUSE_DATABASE_PATH=/absolute/path/to/clause.sqlite3
CLAUSE_DEBUG=true
```

## Notes

- The local bills store lives in SQLite.
- California Code and U.S. Code are queried from external PostgreSQL corpora.
- `scripts/build_gemini_vectors.py` incrementally fills missing bill embeddings.
