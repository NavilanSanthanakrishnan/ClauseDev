#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from step4.config import get_settings
from step4.services.legal_index import alias_forms, extract_references, normalize_citation


def ensure_database_exists() -> None:
    settings = get_settings()
    admin_dsn = (
        f"host={settings.legal_index_postgres_host} "
        f"port={settings.legal_index_postgres_port} "
        f"dbname=postgres "
        f"user={settings.legal_index_postgres_user}"
    )
    if settings.legal_index_postgres_password:
        admin_dsn += f" password={settings.legal_index_postgres_password}"
    with psycopg.connect(admin_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            exists = cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (settings.legal_index_postgres_db,),
            ).fetchone()
            if not exists:
                cursor.execute(f'CREATE DATABASE "{settings.legal_index_postgres_db}"')


def load_schema() -> None:
    settings = get_settings()
    schema_path = ROOT / "sql" / "schema_legal_index.sql"
    with psycopg.connect(settings.legal_index_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_path.read_text())


def _stream_query_rows(dsn: str, query: str, *, fetch_size: int) -> Iterator[dict]:
    with psycopg.connect(dsn, row_factory=dict_row) as connection:
        with connection.cursor(name="stream_cursor") as cursor:
            cursor.execute(query)
            while True:
                rows = cursor.fetchmany(fetch_size)
                if not rows:
                    break
                for row in rows:
                    yield row


def _california_rows(*, fetch_size: int) -> Iterator[dict]:
    settings = get_settings()
    query = """
        SELECT
            section_id,
            code_abbrev,
            code_name,
            citation,
            section_number,
            heading,
            hierarchy_path,
            display_url,
            source_page_url,
            body_text,
            history_text,
            source_count,
            division_name,
            chapter_name,
            article_name,
            division,
            title_num,
            part_num,
            chapter_num,
            article_num,
            active_flg,
            effective_date
        FROM section_search
    """
    return _stream_query_rows(settings.california_dsn, query, fetch_size=fetch_size)


def _uscode_section_rows(*, fetch_size: int) -> Iterator[dict]:
    settings = get_settings()
    query = """
        SELECT
            identifier,
            parent_identifier,
            title_number,
            kind,
            num_value,
            label,
            heading,
            citation,
            cornell_url,
            breadcrumb,
            breadcrumb_json,
            sort_order,
            source_file,
            release_point,
            status,
            notes_text,
            source_credit_text,
            content_text,
            full_text,
            updated_at
        FROM usc_sections
    """
    return _stream_query_rows(settings.uscode_dsn, query, fetch_size=fetch_size)


def _uscode_provision_rows(*, fetch_size: int) -> Iterator[dict]:
    settings = get_settings()
    query = """
        SELECT
            identifier,
            section_identifier,
            parent_identifier,
            title_number,
            kind,
            num_value,
            heading,
            citation,
            depth,
            sort_order,
            direct_text,
            full_text,
            updated_at
        FROM usc_provisions
    """
    return _stream_query_rows(settings.uscode_dsn, query, fetch_size=fetch_size)


def _reset_index() -> None:
    settings = get_settings()
    with psycopg.connect(settings.legal_index_dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("TRUNCATE legal_references, legal_aliases, legal_documents")


def _insert_documents(connection: psycopg.Connection, rows: Iterator[dict], *, source: str, batch_size: int) -> tuple[int, int]:
    inserted_docs = 0
    inserted_refs = 0
    with connection.cursor() as cursor:
        for row in rows:
            if source == "california":
                document_id = f"california:section:{row['section_id']}"
                citation = row["citation"]
                title_label = row["code_name"]
                body_text = "\n\n".join(part for part in [row["body_text"], row["history_text"]] if part)
                metadata = {
                    "code_abbrev": row["code_abbrev"],
                    "code_name": row["code_name"],
                    "section_number": row["section_number"],
                    "source_page_url": row["source_page_url"],
                    "source_count": row["source_count"],
                    "division_name": row["division_name"],
                    "chapter_name": row["chapter_name"],
                    "article_name": row["article_name"],
                    "division": row["division"],
                    "title_num": row["title_num"],
                    "part_num": row["part_num"],
                    "chapter_num": row["chapter_num"],
                    "article_num": row["article_num"],
                }
                cursor.execute(
                    """
                    INSERT INTO legal_documents (
                        document_id, source_system, source_family, source_kind, jurisdiction,
                        citation, normalized_citation, title_number, title_label, heading, hierarchy_path,
                        source_url, body_text, effective_date, active_flag, metadata
                    ) VALUES (
                        %(document_id)s, 'california', 'ca_code', 'section', 'CA',
                        %(citation)s, %(normalized_citation)s, %(title_number)s, %(title_label)s, %(heading)s, %(hierarchy_path)s,
                        %(source_url)s, %(body_text)s, %(effective_date)s, %(active_flag)s, %(metadata)s
                    )
                    """,
                    {
                        "document_id": document_id,
                        "citation": citation,
                        "normalized_citation": normalize_citation(citation),
                        "title_number": row["title_num"],
                        "title_label": title_label,
                        "heading": row["heading"],
                        "hierarchy_path": row["hierarchy_path"],
                        "source_url": row["display_url"],
                        "body_text": body_text,
                        "effective_date": row["effective_date"],
                        "active_flag": row["active_flg"],
                        "metadata": json.dumps(metadata),
                    },
                )
            elif source == "uscode_section":
                document_id = f"federal:usc_section:{row['identifier']}"
                citation = row["citation"]
                body_text = row["full_text"] or row["content_text"] or ""
                metadata = {
                    "identifier": row["identifier"],
                    "parent_identifier": row["parent_identifier"],
                    "kind": row["kind"],
                    "num_value": row["num_value"],
                    "label": row["label"],
                    "breadcrumb_json": row["breadcrumb_json"],
                    "sort_order": row["sort_order"],
                    "source_file": row["source_file"],
                    "release_point": row["release_point"],
                    "status": row["status"],
                    "notes_text": row["notes_text"],
                    "source_credit_text": row["source_credit_text"],
                }
                cursor.execute(
                    """
                    INSERT INTO legal_documents (
                        document_id, source_system, source_family, source_kind, jurisdiction,
                        citation, normalized_citation, title_number, title_label, heading, hierarchy_path,
                        source_url, body_text, effective_date, active_flag, metadata
                    ) VALUES (
                        %(document_id)s, 'federal', 'us_code', 'section', 'US',
                        %(citation)s, %(normalized_citation)s, %(title_number)s, %(title_label)s, %(heading)s, %(hierarchy_path)s,
                        %(source_url)s, %(body_text)s, %(effective_date)s, %(active_flag)s, %(metadata)s
                    )
                    """,
                    {
                        "document_id": document_id,
                        "citation": citation,
                        "normalized_citation": normalize_citation(citation),
                        "title_number": str(row["title_number"]) if row["title_number"] is not None else None,
                        "title_label": f"Title {row['title_number']} U.S. Code" if row["title_number"] is not None else "U.S. Code",
                        "heading": row["heading"] or row["label"],
                        "hierarchy_path": row["breadcrumb"],
                        "source_url": row["cornell_url"],
                        "body_text": body_text,
                        "effective_date": row["updated_at"].isoformat() if row["updated_at"] else None,
                        "active_flag": row["status"] == "active" if row["status"] else None,
                        "metadata": json.dumps(metadata),
                    },
                )
            else:
                document_id = f"federal:usc_provision:{row['identifier']}"
                citation = row["citation"]
                body_text = row["full_text"] or row["direct_text"] or ""
                metadata = {
                    "identifier": row["identifier"],
                    "section_identifier": row["section_identifier"],
                    "parent_identifier": row["parent_identifier"],
                    "kind": row["kind"],
                    "num_value": row["num_value"],
                    "depth": row["depth"],
                    "sort_order": row["sort_order"],
                }
                cursor.execute(
                    """
                    INSERT INTO legal_documents (
                        document_id, source_system, source_family, source_kind, jurisdiction,
                        citation, normalized_citation, title_number, title_label, heading, hierarchy_path,
                        source_url, body_text, effective_date, active_flag, metadata
                    ) VALUES (
                        %(document_id)s, 'federal', 'us_code', 'provision', 'US',
                        %(citation)s, %(normalized_citation)s, %(title_number)s, %(title_label)s, %(heading)s, %(hierarchy_path)s,
                        %(source_url)s, %(body_text)s, %(effective_date)s, %(active_flag)s, %(metadata)s
                    )
                    """,
                    {
                        "document_id": document_id,
                        "citation": citation,
                        "normalized_citation": normalize_citation(citation),
                        "title_number": str(row["title_number"]) if row["title_number"] is not None else None,
                        "title_label": f"Title {row['title_number']} U.S. Code" if row["title_number"] is not None else "U.S. Code",
                        "heading": row["heading"],
                        "hierarchy_path": f"Provision under {row['section_identifier']}",
                        "source_url": None,
                        "body_text": body_text,
                        "effective_date": row["updated_at"].isoformat() if row["updated_at"] else None,
                        "active_flag": True,
                        "metadata": json.dumps(metadata),
                    },
                )

            for alias in alias_forms(citation):
                cursor.execute(
                    """
                    INSERT INTO legal_aliases (document_id, alias, normalized_alias, alias_kind)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (document_id, alias, normalize_citation(alias), "citation"),
                )

            for ref in extract_references(body_text):
                cursor.execute(
                    """
                    INSERT INTO legal_references (
                        document_id, referenced_citation, normalized_referenced_citation, reference_text, reference_type
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        ref.referenced_citation,
                        ref.normalized_referenced_citation,
                        ref.reference_text,
                        ref.reference_type,
                    ),
                )
                inserted_refs += 1
            inserted_docs += 1
            if inserted_docs % batch_size == 0:
                connection.commit()
                print(f"{source}: inserted {inserted_docs} docs", flush=True)
        connection.commit()
    return inserted_docs, inserted_refs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the canonical Clause legal index from California and U.S. Code databases.")
    parser.add_argument("--skip-provisions", action="store_true", help="Skip USC provision rows for a lighter initial index.")
    parser.add_argument("--fetch-size", type=int, default=1000, help="Source rows to fetch per database round-trip.")
    parser.add_argument("--batch-size", type=int, default=500, help="Target documents to commit per batch.")
    parser.add_argument("--resume", action="store_true", help="Append to the existing legal index instead of truncating it.")
    args = parser.parse_args()

    ensure_database_exists()
    if args.resume:
        print("Resuming existing clause_legal_index build", flush=True)
    else:
        load_schema()
        _reset_index()

    california_rows = _california_rows(fetch_size=args.fetch_size)
    uscode_sections = _uscode_section_rows(fetch_size=args.fetch_size)
    uscode_provisions = iter(()) if args.skip_provisions else _uscode_provision_rows(fetch_size=args.fetch_size)

    settings = get_settings()
    with psycopg.connect(settings.legal_index_dsn) as connection:
        cal_docs, cal_refs = _insert_documents(connection, california_rows, source="california", batch_size=args.batch_size)
        usc_docs, usc_refs = _insert_documents(connection, uscode_sections, source="uscode_section", batch_size=args.batch_size)
        prov_docs, prov_refs = _insert_documents(connection, uscode_provisions, source="uscode_provision", batch_size=args.batch_size)

        with connection.cursor() as cursor:
            counts = cursor.execute(
                """
                SELECT
                    (SELECT count(*) FROM legal_documents),
                    (SELECT count(*) FROM legal_aliases),
                    (SELECT count(*) FROM legal_references)
                """
            ).fetchone()

    print("Built clause_legal_index")
    print(f"  california documents: {cal_docs}")
    print(f"  uscode sections: {usc_docs}")
    print(f"  uscode provisions: {prov_docs}")
    print(f"  inserted references: {cal_refs + usc_refs + prov_refs}")
    print(f"  total documents: {counts[0]}")
    print(f"  total aliases: {counts[1]}")
    print(f"  total references: {counts[2]}")


if __name__ == "__main__":
    main()
