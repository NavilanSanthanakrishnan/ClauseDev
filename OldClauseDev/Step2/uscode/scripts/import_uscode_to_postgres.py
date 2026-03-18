#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import sqlite3
import subprocess
from pathlib import Path

USCODE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SQLITE_DB = USCODE_ROOT / "uscode_local.db"
DEFAULT_SCHEMA_SQL = USCODE_ROOT / "postgres_schema.sql"
DEFAULT_POSTLOAD_SQL = USCODE_ROOT / "postgres_postload.sql"

TABLE_COLUMNS = {
    "usc_meta": [
        "key",
        "value",
    ],
    "usc_nodes": [
        "identifier",
        "parent_identifier",
        "title_number",
        "kind",
        "num_value",
        "label",
        "heading",
        "citation",
        "cornell_url",
        "breadcrumb",
        "breadcrumb_json",
        "sort_order",
        "source_file",
        "release_point",
        "status",
        "notes_text",
        "source_credit_text",
        "content_text",
        "full_text",
        "updated_at",
    ],
    "usc_provisions": [
        "identifier",
        "section_identifier",
        "parent_identifier",
        "title_number",
        "kind",
        "num_value",
        "heading",
        "citation",
        "depth",
        "sort_order",
        "direct_text",
        "full_text",
        "updated_at",
    ],
    "usc_references": [
        "source_table",
        "source_identifier",
        "target_href",
        "target_identifier",
        "target_citation",
        "anchor_text",
        "updated_at",
    ],
}


def run_psql(
    *,
    host: str,
    port: int,
    user: str,
    database: str,
    sql: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            database,
            "-c",
            sql,
        ],
        text=True,
        capture_output=True,
        check=True,
    )


def recreate_database(
    *,
    host: str,
    port: int,
    user: str,
    maintenance_db: str,
    database: str,
) -> None:
    run_psql(
        host=host,
        port=port,
        user=user,
        database=maintenance_db,
        sql=f"""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = '{database}'
          AND pid <> pg_backend_pid();
        """,
    )
    run_psql(
        host=host,
        port=port,
        user=user,
        database=maintenance_db,
        sql=f'DROP DATABASE IF EXISTS "{database}";',
    )
    run_psql(
        host=host,
        port=port,
        user=user,
        database=maintenance_db,
        sql=f'CREATE DATABASE "{database}";',
    )


def apply_schema(
    *,
    host: str,
    port: int,
    user: str,
    database: str,
    schema_sql_path: Path,
) -> None:
    sql = schema_sql_path.read_text(encoding="utf-8")
    subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            database,
        ],
        input=sql,
        text=True,
        check=True,
    )


def apply_sql_file(
    *,
    host: str,
    port: int,
    user: str,
    database: str,
    sql_path: Path,
) -> None:
    sql = sql_path.read_text(encoding="utf-8")
    subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            database,
        ],
        input=sql,
        text=True,
        check=True,
    )


def query_scalar(
    *,
    host: str,
    port: int,
    user: str,
    database: str,
    sql: str,
) -> str:
    result = subprocess.run(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-At",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            database,
            "-c",
            sql,
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def copy_table(
    *,
    sqlite_conn: sqlite3.Connection,
    table_name: str,
    columns: list[str],
    host: str,
    port: int,
    user: str,
    database: str,
) -> int:
    query = f"SELECT {', '.join(columns)} FROM {table_name}"
    cursor = sqlite_conn.execute(query)

    copy_sql = (
        f"COPY public.{table_name} ({', '.join(columns)}) "
        "FROM STDIN WITH (FORMAT csv, NULL '\\N')"
    )
    process = subprocess.Popen(
        [
            "psql",
            "-v",
            "ON_ERROR_STOP=1",
            "-h",
            host,
            "-p",
            str(port),
            "-U",
            user,
            "-d",
            database,
            "-c",
            copy_sql,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    if process.stdin is None:
        raise RuntimeError(f"Failed to open stdin for COPY on {table_name}")

    writer = csv.writer(process.stdin, lineterminator="\n")
    row_count = 0
    try:
        for row in cursor:
            writer.writerow("\\N" if value is None else value for value in row)
            row_count += 1
            if row_count % 100000 == 0:
                print(f"{table_name}: copied {row_count:,} rows", flush=True)
    finally:
        process.stdin.close()

    stdout = process.stdout.read() if process.stdout is not None else ""
    stderr = process.stderr.read() if process.stderr is not None else ""
    process.wait()
    if process.returncode != 0:
        raise RuntimeError(
            f"psql COPY failed for {table_name} with code {process.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
        )

    print(f"{table_name}: copied {row_count:,} rows", flush=True)
    return row_count


def analyze_tables(
    *,
    host: str,
    port: int,
    user: str,
    database: str,
) -> None:
    run_psql(
        host=host,
        port=port,
        user=user,
        database=database,
        sql="""
        ANALYZE public.usc_meta;
        ANALYZE public.usc_nodes;
        ANALYZE public.usc_provisions;
        ANALYZE public.usc_references;
        """,
    )


def verify_counts(
    *,
    sqlite_conn: sqlite3.Connection,
    host: str,
    port: int,
    user: str,
    database: str,
) -> list[tuple[str, int, int]]:
    results: list[tuple[str, int, int]] = []
    for table_name in TABLE_COLUMNS:
        sqlite_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        pg_value = int(
            query_scalar(
                host=host,
                port=port,
                user=user,
                database=database,
                sql=f"SELECT COUNT(*) FROM public.{table_name};",
            )
        )
        results.append((table_name, sqlite_count, pg_value))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream the local SQLite U.S. Code corpus into PostgreSQL for Postico or other SQL tooling."
    )
    parser.add_argument("--sqlite-db", default=str(DEFAULT_SQLITE_DB), help="Path to the SQLite source database.")
    parser.add_argument("--schema-sql", default=str(DEFAULT_SCHEMA_SQL), help="PostgreSQL schema SQL file.")
    parser.add_argument("--postload-sql", default=str(DEFAULT_POSTLOAD_SQL), help="PostgreSQL SQL run after bulk copy.")
    parser.add_argument("--pg-host", default="127.0.0.1", help="PostgreSQL host.")
    parser.add_argument("--pg-port", type=int, default=55432, help="PostgreSQL port.")
    parser.add_argument("--pg-user", default="navilan", help="PostgreSQL user.")
    parser.add_argument("--pg-database", default="uscode_local", help="Target PostgreSQL database.")
    parser.add_argument("--pg-maintenance-db", default="postgres", help="Maintenance database used for create/drop.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the target database before loading.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Reuse the existing database and truncate the U.S. Code tables before loading.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sqlite_db = Path(args.sqlite_db)
    schema_sql = Path(args.schema_sql)
    postload_sql = Path(args.postload_sql)
    if not sqlite_db.exists():
        raise FileNotFoundError(f"SQLite DB not found: {sqlite_db}")
    if not schema_sql.exists():
        raise FileNotFoundError(f"Schema SQL not found: {schema_sql}")
    if not postload_sql.exists():
        raise FileNotFoundError(f"Post-load SQL not found: {postload_sql}")

    if args.recreate:
        print(f"Recreating PostgreSQL database {args.pg_database} on {args.pg_host}:{args.pg_port}", flush=True)
        recreate_database(
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            maintenance_db=args.pg_maintenance_db,
            database=args.pg_database,
        )
        apply_schema(
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            database=args.pg_database,
            schema_sql_path=schema_sql,
        )
    elif args.reload:
        print(f"Reloading existing PostgreSQL database {args.pg_database}", flush=True)
        apply_schema(
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            database=args.pg_database,
            schema_sql_path=schema_sql,
        )
    else:
        run_psql(
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            database=args.pg_maintenance_db,
            sql=f"SELECT 1 FROM pg_database WHERE datname = '{args.pg_database}';",
        )

    sqlite_conn = sqlite3.connect(sqlite_db)
    try:
        for table_name, columns in TABLE_COLUMNS.items():
            copy_table(
                sqlite_conn=sqlite_conn,
                table_name=table_name,
                columns=columns,
                host=args.pg_host,
                port=args.pg_port,
                user=args.pg_user,
                database=args.pg_database,
            )

        apply_sql_file(
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            database=args.pg_database,
            sql_path=postload_sql,
        )
        analyze_tables(
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            database=args.pg_database,
        )
        verification = verify_counts(
            sqlite_conn=sqlite_conn,
            host=args.pg_host,
            port=args.pg_port,
            user=args.pg_user,
            database=args.pg_database,
        )
    finally:
        sqlite_conn.close()

    print("\nVerification", flush=True)
    for table_name, sqlite_count, pg_count in verification:
        status = "OK" if sqlite_count == pg_count else "MISMATCH"
        print(
            f"{table_name}: sqlite={sqlite_count:,} postgres={pg_count:,} [{status}]",
            flush=True,
        )

    print(
        f"\nPostico connection: host={args.pg_host} port={args.pg_port} db={args.pg_database} user={args.pg_user}",
        flush=True,
    )


if __name__ == "__main__":
    main()
