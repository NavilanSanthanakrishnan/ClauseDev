This directory holds generated U.S. Code artifacts for local use.

Expected files:

- `uscode_local.db`: SQLite database built from the official OLRC XML release.
- `xml_uscAll_current.zip`: cached source archive from `uscode.house.gov`.

Build commands:

```bash
cd /Users/navilan/Documents/Clause/Step2
python3 uscode/scripts/build_uscode_db.py
python3 uscode/scripts/query_uscode_db.py stats
python3 uscode/scripts/query_uscode_db.py search "clean vehicle credit"
python3 uscode/scripts/query_uscode_db.py show --citation "26 U.S.C. § 30D"
```

PostgreSQL import:

```bash
cd /Users/navilan/Documents/Clause/Step2
python3 uscode/scripts/import_uscode_to_postgres.py --recreate
```

Local Postico target:

- host: `127.0.0.1`
- port: `55432`
- database: `uscode_local`
- user: `navilan`
