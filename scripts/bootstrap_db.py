#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from psycopg import connect

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step1.config import get_settings


def main() -> None:
    settings = get_settings()
    sql_path = Path(__file__).resolve().parents[1] / "sql" / "bootstrap_openstates_step1.sql"
    sql_text = sql_path.read_text(encoding="utf-8")
    print(f"Applying {sql_path} to {settings.postgres_db} on {settings.postgres_host}:{settings.postgres_port}")
    with connect(settings.postgres_dsn, autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql_text)
    print("Bootstrap complete.")


if __name__ == "__main__":
    main()
