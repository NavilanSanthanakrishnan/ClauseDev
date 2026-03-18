#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from psycopg import connect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step1.config import get_settings


REQUIRED_SOURCE_TABLES = (
    "public.opencivicdata_bill",
    "public.opencivicdata_legislativesession",
    "public.opencivicdata_jurisdiction",
    "public.opencivicdata_searchablebill",
    "public.opencivicdata_billsource",
    "public.opencivicdata_billversion",
    "public.opencivicdata_billversionlink",
    "public.opencivicdata_billdocument",
    "public.opencivicdata_billdocumentlink",
    "public.opencivicdata_voteevent",
    "public.opencivicdata_votecount",
)


def _missing_source_tables(cursor) -> list[str]:
    missing: list[str] = []
    for name in REQUIRED_SOURCE_TABLES:
        cursor.execute("SELECT to_regclass(%s) AS regclass", (name,))
        row = cursor.fetchone()
        if not row or row[0] is None:
            missing.append(name)
    return missing


def main() -> None:
    settings = get_settings()
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "bootstrap_openstates_step1.sql"
    sql_text = sql_path.read_text(encoding="utf-8")
    print(f"Applying {sql_path} to {settings.postgres_db} on {settings.postgres_host}:{settings.postgres_port}")
    with connect(settings.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cursor:
            missing_tables = _missing_source_tables(cursor)
            if missing_tables:
                missing = ", ".join(missing_tables)
                raise SystemExit(
                    "OpenStates source tables were not found in the target database. "
                    f"Missing: {missing}"
                )
            cursor.execute(sql_text)
    print("Bootstrap complete.")


if __name__ == "__main__":
    main()
