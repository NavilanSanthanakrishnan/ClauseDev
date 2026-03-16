#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import psycopg


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sql" / "schema_california_code_postgres.sql"

TABLE_ORDER = (
    "code_books",
    "toc_files",
    "article_refs",
    "source_pages",
    "sections",
    "section_sources",
    "section_collisions",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync the Step4 California code dataset from SQLite into PostgreSQL.")
    parser.add_argument(
        "--sqlite-db",
        default=str(ROOT / "data" / "california_code.db"),
        help="Source SQLite database path.",
    )
    parser.add_argument(
        "--pg-dsn",
        default="host=127.0.0.1 port=55432 dbname=california_code user=navilan",
        help="Target PostgreSQL DSN.",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Truncate the PostgreSQL tables before loading.",
    )
    return parser


def sqlite_table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def normalize_row(table: str, columns: list[str], row: sqlite3.Row) -> tuple[object, ...]:
    values = []
    for column in columns:
        value = row[column]
        if table == "section_sources" and column == "article_ref_id" and value is None:
            values.append(None)
            continue
        values.append(value)
    return tuple(values)


def main() -> None:
    args = build_parser().parse_args()
    sqlite_db = Path(args.sqlite_db).expanduser().resolve()
    if not sqlite_db.exists():
        raise SystemExit(f"SQLite DB does not exist: {sqlite_db}")

    sqlite_conn = sqlite3.connect(sqlite_db)
    sqlite_conn.row_factory = sqlite3.Row

    with psycopg.connect(args.pg_dsn, autocommit=True) as pg_conn:
        with pg_conn.cursor() as cursor:
            cursor.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
            if args.truncate:
                cursor.execute(
                    """
                    TRUNCATE TABLE
                        section_collisions,
                        section_sources,
                        sections,
                        source_pages,
                        article_refs,
                        toc_files,
                        code_books
                    RESTART IDENTITY CASCADE
                    """
                )

            for table in TABLE_ORDER:
                columns = sqlite_table_columns(sqlite_conn, table)
                column_list = ", ".join(columns)
                placeholders = ", ".join(["%s"] * len(columns))
                insert_sql = f"INSERT INTO {table} ({column_list}) VALUES ({placeholders})"

                rows = sqlite_conn.execute(f"SELECT {column_list} FROM {table} ORDER BY 1").fetchall()
                if not rows:
                    print(f"{table}: 0 rows", flush=True)
                    continue

                batch = [normalize_row(table, columns, row) for row in rows]
                with pg_conn.cursor() as insert_cursor:
                    insert_cursor.executemany(insert_sql, batch)
                print(f"{table}: {len(batch)} rows", flush=True)

            with pg_conn.cursor() as cursor2:
                cursor2.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM code_books),
                        (SELECT COUNT(*) FROM toc_files),
                        (SELECT COUNT(*) FROM article_refs),
                        (SELECT COUNT(*) FROM source_pages),
                        (SELECT COUNT(*) FROM sections)
                    """
                )
                counts = cursor2.fetchone()
                print(
                    "postgres_counts:",
                    {
                        "code_books": counts[0],
                        "toc_files": counts[1],
                        "article_refs": counts[2],
                        "source_pages": counts[3],
                        "sections": counts[4],
                    },
                    flush=True,
                )

    sqlite_conn.close()


if __name__ == "__main__":
    sys.exit(main())
