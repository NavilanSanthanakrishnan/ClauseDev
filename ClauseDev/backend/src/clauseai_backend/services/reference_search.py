from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from clauseai_backend.db.session import ReferenceDatabases


def _safe_query(db: Session, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        rows = db.execute(text(sql), params).mappings().all()
    except SQLAlchemyError:
        return []
    return [_json_safe(dict(row)) for row in rows]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _query_patterns(query_text: str) -> dict[str, str]:
    tokens: list[str] = []
    for token in query_text.split():
        cleaned = "".join(ch for ch in token if ch.isalnum() or ch in {"-", "_"}).strip().lower()
        if len(cleaned) < 3 or cleaned in tokens:
            continue
        tokens.append(cleaned)
        if len(tokens) == 3:
            break
    while len(tokens) < 3:
        tokens.append("")
    return {
        "pattern_full": f"%{query_text}%",
        "pattern_one": f"%{tokens[0]}%" if tokens[0] else "",
        "pattern_two": f"%{tokens[1]}%" if tokens[1] else "",
        "pattern_three": f"%{tokens[2]}%" if tokens[2] else "",
    }


def search_bills(
    db: ReferenceDatabases, query: str, limit: int, *, status: str | None = None, state_code: str | None = None
) -> list[dict[str, Any]]:
    query_text = query.strip()
    if not query_text:
        return []
    patterns = _query_patterns(query_text)
    return _safe_query(
        db.openstates,
        """
        with abstracts as (
            select bill_id, string_agg(abstract, E'\n\n' order by id::text) as summary_text
            from public.opencivicdata_billabstract
            group by bill_id
        ),
        latest_source as (
            select distinct on (bill_id) bill_id, url
            from public.opencivicdata_billsource
            order by bill_id, id desc
        ),
        base as (
            select
            b.id as bill_id,
            b.identifier,
            b.title,
            coalesce(a.summary_text, b.title) as summary_text,
            j.name as jurisdiction_name,
            case
                when j.id like '%/state:%' then lower(split_part(split_part(j.id, '/state:', 2), '/', 1))
                else null
            end as state_code,
            case
                when lower(coalesce(b.latest_action_description, '')) like '%chapter%'
                  or lower(coalesce(b.latest_action_description, '')) like '%signed%'
                  or lower(coalesce(b.latest_action_description, '')) like '%became law%'
                  or lower(coalesce(b.latest_action_description, '')) like '%approved by governor%'
                then 'enacted'
                when lower(coalesce(b.latest_action_description, '')) like '%veto%'
                then 'vetoed'
                when lower(coalesce(b.latest_action_description, '')) like '%failed%'
                  or lower(coalesce(b.latest_action_description, '')) like '%died%'
                  or lower(coalesce(b.latest_action_description, '')) like '%dead%'
                  or lower(coalesce(b.latest_action_description, '')) like '%indefinitely postponed%'
                  or lower(coalesce(b.latest_action_description, '')) like '%defeated%'
                  or lower(coalesce(b.latest_action_description, '')) like '%rejected%'
                  or lower(coalesce(b.latest_action_description, '')) like '%withdrawn%'
                then 'failed_or_dead'
                when b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                then 'passed_not_enacted'
                else 'other_or_in_progress'
            end as derived_status,
            case when b.latest_action_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then b.latest_action_date::date end as latest_action_date,
            ls.url as primary_source_url
            from public.opencivicdata_bill b
            join public.opencivicdata_legislativesession s on s.id = b.legislative_session_id
            join public.opencivicdata_jurisdiction j on j.id = s.jurisdiction_id
            left join abstracts a on a.bill_id = b.id
            left join latest_source ls on ls.bill_id = b.id
            where 'bill' = any(b.classification)
        )
        select
            bill_id,
            identifier,
            title,
            summary_text,
            jurisdiction_name,
            state_code,
            derived_status,
            latest_action_date,
            primary_source_url
        from (
            select
                *,
                (
                    case when identifier ilike :pattern_full or title ilike :pattern_full or summary_text ilike :pattern_full then 5 else 0 end
                    + case when :pattern_one <> '' and (identifier ilike :pattern_one or title ilike :pattern_one or summary_text ilike :pattern_one) then 2 else 0 end
                    + case when :pattern_two <> '' and (identifier ilike :pattern_two or title ilike :pattern_two or summary_text ilike :pattern_two) then 1 else 0 end
                    + case when :pattern_three <> '' and (identifier ilike :pattern_three or title ilike :pattern_three or summary_text ilike :pattern_three) then 1 else 0 end
                ) as score
            from base
        ) ranked
        where (
            identifier ilike :pattern_full
            or
            title ilike :pattern_full
            or summary_text ilike :pattern_full
            or (:pattern_one <> '' and (identifier ilike :pattern_one or title ilike :pattern_one or summary_text ilike :pattern_one))
            or (:pattern_two <> '' and (identifier ilike :pattern_two or title ilike :pattern_two or summary_text ilike :pattern_two))
            or (:pattern_three <> '' and (identifier ilike :pattern_three or title ilike :pattern_three or summary_text ilike :pattern_three))
        )
          and (:status = '' or derived_status = :status)
          and (:state_code = '' or state_code = :state_code)
        order by score desc, latest_action_date desc nulls last
        limit :limit
        """,
        {
            "limit": limit,
            "status": (status or "").strip(),
            "state_code": (state_code or "").strip().lower(),
            **patterns,
        },
    )


def get_bill_detail(db: ReferenceDatabases, bill_id: str) -> dict[str, Any] | None:
    rows = _safe_query(
        db.openstates,
        """
        with abstracts as (
            select bill_id, string_agg(abstract, E'\n\n' order by id::text) as summary_text
            from public.opencivicdata_billabstract
            group by bill_id
        ),
        latest_source as (
            select distinct on (bill_id) bill_id, url
            from public.opencivicdata_billsource
            order by bill_id, id desc
        )
        select
            b.id as bill_id,
            b.identifier,
            b.title,
            coalesce(a.summary_text, b.title) as summary_text,
            j.name as jurisdiction_name,
            case
                when j.id like '%/state:%' then lower(split_part(split_part(j.id, '/state:', 2), '/', 1))
                else null
            end as state_code,
            case
                when lower(coalesce(b.latest_action_description, '')) like '%chapter%'
                  or lower(coalesce(b.latest_action_description, '')) like '%signed%'
                  or lower(coalesce(b.latest_action_description, '')) like '%became law%'
                  or lower(coalesce(b.latest_action_description, '')) like '%approved by governor%'
                then 'enacted'
                when lower(coalesce(b.latest_action_description, '')) like '%veto%'
                then 'vetoed'
                when lower(coalesce(b.latest_action_description, '')) like '%failed%'
                  or lower(coalesce(b.latest_action_description, '')) like '%died%'
                  or lower(coalesce(b.latest_action_description, '')) like '%dead%'
                  or lower(coalesce(b.latest_action_description, '')) like '%indefinitely postponed%'
                  or lower(coalesce(b.latest_action_description, '')) like '%defeated%'
                  or lower(coalesce(b.latest_action_description, '')) like '%rejected%'
                  or lower(coalesce(b.latest_action_description, '')) like '%withdrawn%'
                then 'failed_or_dead'
                when b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                then 'passed_not_enacted'
                else 'other_or_in_progress'
            end as derived_status,
            s.identifier as session_identifier,
            case when b.latest_action_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then b.latest_action_date::date end as latest_action_date,
            case when b.latest_passage_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then b.latest_passage_date::date end as latest_passage_date,
            ls.url as primary_source_url,
            null::text as full_text
        from public.opencivicdata_bill b
        join public.opencivicdata_legislativesession s on s.id = b.legislative_session_id
        join public.opencivicdata_jurisdiction j on j.id = s.jurisdiction_id
        left join abstracts a on a.bill_id = b.id
        left join latest_source ls on ls.bill_id = b.id
        where b.id = :bill_id
        limit 1
        """,
        {"bill_id": bill_id},
    )
    return rows[0] if rows else None


def search_laws(db: ReferenceDatabases, query: str, limit: int, *, jurisdiction: str | None = None) -> list[dict[str, Any]]:
    query_text = query.strip()
    if not query_text:
        return []
    normalized_jurisdiction = (jurisdiction or "").strip()
    patterns = _query_patterns(query_text)
    legal_index_hits = _safe_query(
        db.legal_index,
        """
        select
            'legal_index:' || document_id as document_id,
            citation,
            heading,
            jurisdiction,
            hierarchy_path,
            source_url,
            left(body_text, 900) as body_excerpt
        from public.legal_documents
        where (
            search_text @@ websearch_to_tsquery('english', :query_text)
            or citation ilike :pattern_full
            or coalesce(heading, '') ilike :pattern_full
        )
          and (:jurisdiction = '' or jurisdiction = :jurisdiction)
        order by ts_rank_cd(search_text, websearch_to_tsquery('english', :query_text)) desc, citation
        limit :limit
        """,
        {"query_text": query_text, "limit": limit, "jurisdiction": normalized_jurisdiction, **patterns},
    )
    california_hits = _safe_query(
        db.california_code,
        """
        select
            'ca_code:' || id as document_id,
            law_code || ' ' || section_num as citation,
            null::text as heading,
            'California' as jurisdiction,
            concat_ws(' > ', division, title_num, part_num, chapter_num, article_num) as hierarchy_path,
            display_url as source_url,
            left(content_text, 900) as body_excerpt
        from public.official_law_sections
        where (
            search_vector @@ websearch_to_tsquery('english', :query_text)
            or (law_code || ' ' || section_num) ilike :pattern_full
        )
          and (:jurisdiction = '' or :jurisdiction in ('California', 'CA'))
        order by ts_rank_cd(search_vector, websearch_to_tsquery('english', :query_text)) desc, law_code, section_num
        limit :limit
        """,
        {"query_text": query_text, "limit": limit, "jurisdiction": normalized_jurisdiction, **patterns},
    )
    uscode_hits = _safe_query(
        db.uscode,
        """
        select
            'uscode:' || identifier as document_id,
            citation,
            heading as heading,
            'United States' as jurisdiction,
            breadcrumb as hierarchy_path,
            cornell_url as source_url,
            left(coalesce(full_text, content_text, ''), 900) as body_excerpt
        from public.usc_nodes
        where kind = 'section'
          and (
            citation ilike :pattern_full
            or coalesce(heading, '') ilike :pattern_full
            or (:pattern_one <> '' and (citation ilike :pattern_one or coalesce(heading, '') ilike :pattern_one or coalesce(full_text, content_text, '') ilike :pattern_one))
            or (:pattern_two <> '' and (citation ilike :pattern_two or coalesce(heading, '') ilike :pattern_two or coalesce(full_text, content_text, '') ilike :pattern_two))
            or (:pattern_three <> '' and (citation ilike :pattern_three or coalesce(heading, '') ilike :pattern_three or coalesce(full_text, content_text, '') ilike :pattern_three))
          )
          and (:jurisdiction = '' or :jurisdiction in ('United States', 'US', 'Federal'))
        order by citation
        limit :limit
        """,
        {"limit": limit, "jurisdiction": normalized_jurisdiction, **patterns},
    )
    return (legal_index_hits + california_hits + uscode_hits)[:limit]


def get_law_detail(db: ReferenceDatabases, document_id: str) -> dict[str, Any] | None:
    if document_id.startswith("legal_index:"):
        rows = _safe_query(
            db.legal_index,
            """
            select
                'legal_index:' || document_id as document_id,
                citation,
                heading,
                jurisdiction,
                hierarchy_path,
                source_url,
                body_text
            from public.legal_documents
            where document_id = :document_id
            limit 1
            """,
            {"document_id": document_id.split(":", 1)[1]},
        )
        return rows[0] if rows else None
    if document_id.startswith("ca_code:"):
        rows = _safe_query(
            db.california_code,
            """
            select
                'ca_code:' || id as document_id,
                law_code || ' ' || section_num as citation,
                null::text as heading,
                'California' as jurisdiction,
                concat_ws(' > ', division, title_num, part_num, chapter_num, article_num) as hierarchy_path,
                display_url as source_url,
                content_text as body_text
            from public.official_law_sections
            where id = :document_id
            limit 1
            """,
            {"document_id": document_id.split(":", 1)[1]},
        )
        return rows[0] if rows else None
    if document_id.startswith("uscode:"):
        rows = _safe_query(
            db.uscode,
            """
            select
                'uscode:' || identifier as document_id,
                citation,
                heading,
                'United States' as jurisdiction,
                breadcrumb as hierarchy_path,
                cornell_url as source_url,
                coalesce(full_text, content_text, '') as body_text
            from public.usc_nodes
            where identifier = :document_id
              and kind = 'section'
            limit 1
            """,
            {"document_id": document_id.split(":", 1)[1]},
        )
        return rows[0] if rows else None
    return None
