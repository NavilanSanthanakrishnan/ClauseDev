from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from clause_backend.core.config import settings


LAW_SOURCES = ("California Code", "United States Code")
LAW_JURISDICTIONS = ("California", "United States")


@contextmanager
def _connect(dsn: str) -> Iterator[psycopg.Connection[Any]]:
    connection = psycopg.connect(dsn, row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()


def _safe_query(dsn: str, sql: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    try:
        with _connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]
    except Exception:
        return []


def _safe_scalar(dsn: str, sql: str) -> int:
    try:
        with _connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                row = cursor.fetchone()
                if not row:
                    return 0
                if isinstance(row, dict):
                    return int(next(iter(row.values())))
                return int(row[0])
    except Exception:
        return 0


def law_stats() -> dict[str, int]:
    california_laws = _safe_scalar(settings.california_code_dsn, "select count(*) from public.official_law_sections")
    federal_laws = _safe_scalar(
        settings.uscode_dsn,
        "select count(*) from public.usc_nodes where kind = 'section'",
    )
    return {
        "total_laws": california_laws + federal_laws,
        "california_laws": california_laws,
        "federal_laws": federal_laws,
    }


def law_filter_options() -> dict[str, list[str]]:
    return {
        "jurisdictions": list(LAW_JURISDICTIONS),
        "sources": list(LAW_SOURCES),
    }


def search_california_laws(query_text: str, limit: int) -> list[dict[str, Any]]:
    exact_hits = _safe_query(
        settings.california_code_dsn,
        """
        select
            'ca_code:' || id as document_id,
            law_code || ' ' || section_num as citation,
            'California' as jurisdiction,
            'California Code' as source,
            null::text as heading,
            concat_ws(' > ', division, title_num, part_num, chapter_num, article_num) as hierarchy_path,
            left(content_text, 1200) as body_excerpt,
            display_url as source_url,
            1.0 as lexical_rank
        from public.official_law_sections
        where (law_code || ' ' || section_num) ilike %s
        order by law_code, section_num
        limit %s
        """,
        (f"%{query_text}%", min(limit, 10)),
    )
    text_hits = _safe_query(
        settings.california_code_dsn,
        """
        select
            'ca_code:' || id as document_id,
            law_code || ' ' || section_num as citation,
            'California' as jurisdiction,
            'California Code' as source,
            null::text as heading,
            concat_ws(' > ', division, title_num, part_num, chapter_num, article_num) as hierarchy_path,
            left(content_text, 1200) as body_excerpt,
            display_url as source_url,
            ts_rank_cd(search_vector, websearch_to_tsquery('english', %s)) as lexical_rank
        from public.official_law_sections
        where search_vector @@ websearch_to_tsquery('english', %s)
        order by lexical_rank desc, law_code, section_num
        limit %s
        """,
        (query_text, query_text, limit),
    )
    merged: dict[str, dict[str, Any]] = {}
    for item in exact_hits + text_hits:
        merged[item["document_id"]] = item
    return list(merged.values())[:limit]


def search_uscode_laws(query_text: str, limit: int) -> list[dict[str, Any]]:
    exact_hits = _safe_query(
        settings.uscode_dsn,
        """
        select
            'uscode:' || identifier as document_id,
            citation,
            'United States' as jurisdiction,
            'United States Code' as source,
            heading,
            breadcrumb as hierarchy_path,
            left(coalesce(full_text, content_text, ''), 1200) as body_excerpt,
            cornell_url as source_url,
            1.0 as lexical_rank
        from public.usc_nodes
        where kind = 'section'
          and (citation ilike %s or coalesce(heading, '') ilike %s)
        order by citation
        limit %s
        """,
        (f"%{query_text}%", f"%{query_text}%", min(limit, 10)),
    )
    text_hits = _safe_query(
        settings.uscode_dsn,
        """
        select
            'uscode:' || identifier as document_id,
            citation,
            'United States' as jurisdiction,
            'United States Code' as source,
            heading,
            breadcrumb as hierarchy_path,
            left(coalesce(full_text, content_text, ''), 1200) as body_excerpt,
            cornell_url as source_url,
            ts_rank_cd(
                to_tsvector(
                    'english',
                    coalesce(citation, '') || ' ' || coalesce(label, '') || ' ' || coalesce(heading, '') || ' ' || coalesce(breadcrumb, '') || ' ' || coalesce(content_text, '') || ' ' || coalesce(full_text, '')
                ),
                websearch_to_tsquery('english', %s)
            ) as lexical_rank
        from public.usc_nodes
        where kind = 'section'
          and to_tsvector(
            'english',
            coalesce(citation, '') || ' ' || coalesce(label, '') || ' ' || coalesce(heading, '') || ' ' || coalesce(breadcrumb, '') || ' ' || coalesce(content_text, '') || ' ' || coalesce(full_text, '')
          ) @@ websearch_to_tsquery('english', %s)
        order by lexical_rank desc, citation
        limit %s
        """,
        (query_text, query_text, limit),
    )
    merged: dict[str, dict[str, Any]] = {}
    for item in exact_hits + text_hits:
        merged[item["document_id"]] = item
    return list(merged.values())[:limit]


def get_california_law(document_id: str) -> dict[str, Any] | None:
    rows = _safe_query(
        settings.california_code_dsn,
        """
        select
            'ca_code:' || id as document_id,
            law_code || ' ' || section_num as citation,
            'California' as jurisdiction,
            'California Code' as source,
            null::text as heading,
            concat_ws(' > ', division, title_num, part_num, chapter_num, article_num) as hierarchy_path,
            content_text as body_text,
            display_url as source_url
        from public.official_law_sections
        where id = %s
        limit 1
        """,
        (document_id,),
    )
    return rows[0] if rows else None


def get_uscode_law(document_id: str) -> dict[str, Any] | None:
    rows = _safe_query(
        settings.uscode_dsn,
        """
        select
            'uscode:' || identifier as document_id,
            citation,
            'United States' as jurisdiction,
            'United States Code' as source,
            heading,
            breadcrumb as hierarchy_path,
            coalesce(full_text, content_text, '') as body_text,
            cornell_url as source_url
        from public.usc_nodes
        where identifier = %s
          and kind = 'section'
        limit 1
        """,
        (document_id,),
    )
    return rows[0] if rows else None
