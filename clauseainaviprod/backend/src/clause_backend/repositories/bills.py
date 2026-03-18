from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from typing import Any

from clause_backend.db import get_connection


def replace_bills(records: list[dict[str, Any]]) -> None:
    with get_connection() as connection:
        connection.execute("delete from bill_vectors")
        connection.execute("delete from bill_fts")
        connection.execute("delete from bills")

        for record in records:
            topics_json = json.dumps(record["topics"])
            search_topics = " ".join(record["topics"])
            connection.execute(
                """
                insert into bills (
                    bill_id,
                    identifier,
                    jurisdiction,
                    state_code,
                    session_name,
                    status,
                    outcome,
                    sponsor,
                    committee,
                    title,
                    summary,
                    excerpt,
                    full_text,
                    source_url,
                    latest_action_date,
                    topics_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["bill_id"],
                    record["identifier"],
                    record["jurisdiction"],
                    record["state_code"],
                    record["session_name"],
                    record["status"],
                    record["outcome"],
                    record["sponsor"],
                    record["committee"],
                    record["title"],
                    record["summary"],
                    record["excerpt"],
                    record["full_text"],
                    record.get("source_url"),
                    record.get("latest_action_date"),
                    topics_json,
                ),
            )
            connection.execute(
                """
                insert into bill_fts (
                    bill_id,
                    identifier,
                    title,
                    summary,
                    full_text,
                    sponsor,
                    committee,
                    jurisdiction,
                    topics
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["bill_id"],
                    record["identifier"],
                    record["title"],
                    record["summary"],
                    record["full_text"],
                    record["sponsor"],
                    record["committee"],
                    record["jurisdiction"],
                    search_topics,
                ),
            )


def get_bill(bill_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        row = connection.execute(
            "select * from bills where bill_id = ? or identifier = ? limit 1",
            (bill_id, bill_id),
        ).fetchone()
        return hydrate_bill(row) if row else None


def list_filter_options() -> dict[str, list[str]]:
    with get_connection() as connection:
        jurisdictions = [
            row[0]
            for row in connection.execute("select distinct jurisdiction from bills order by jurisdiction").fetchall()
        ]
        sessions = [
            row[0]
            for row in connection.execute("select distinct session_name from bills order by session_name desc").fetchall()
        ]
        statuses = [
            row[0]
            for row in connection.execute("select distinct status from bills order by status").fetchall()
        ]
        outcomes = [
            row[0]
            for row in connection.execute("select distinct outcome from bills order by outcome").fetchall()
        ]
    topics = list_top_topics(limit=20)
    return {
        "jurisdictions": jurisdictions,
        "sessions": sessions,
        "statuses": statuses,
        "outcomes": outcomes,
        "topics": topics,
    }


def list_top_topics(limit: int = 10) -> list[str]:
    counts: Counter[str] = Counter()
    with get_connection() as connection:
        rows = connection.execute("select topics_json from bills").fetchall()
    for row in rows:
        counts.update(json.loads(row[0]))
    return [item for item, _ in counts.most_common(limit)]


def database_stats() -> dict[str, Any]:
    with get_connection() as connection:
        total_bills = int(connection.execute("select count(*) from bills").fetchone()[0])
        jurisdictions = int(connection.execute("select count(distinct jurisdiction) from bills").fetchone()[0])
        active_sessions = int(connection.execute("select count(distinct session_name) from bills").fetchone()[0])
    return {
        "total_bills": total_bills,
        "jurisdictions": jurisdictions,
        "active_sessions": active_sessions,
        "top_topics": list_top_topics(limit=6),
    }


def search_exact(query: str, limit: int) -> list[dict[str, Any]]:
    pattern = f"%{query.lower()}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            select *, 120.0 as exact_score
            from bills
            where lower(identifier) = lower(?)
               or lower(title) like ?
               or lower(summary) like ?
            limit ?
            """,
            (query, pattern, pattern, limit),
        ).fetchall()
    return [hydrate_bill(row, extra={"score": float(row["exact_score"])}) for row in rows]


def search_fts(match_query: str, limit: int, filters: dict[str, str | None]) -> list[dict[str, Any]]:
    clauses = []
    params: list[Any] = []
    for key in ("jurisdiction", "session_name", "status", "outcome"):
        value = filters.get(key)
        if value:
            clauses.append(f"b.{key} = ?")
            params.append(value)
    topic = filters.get("topic")
    if topic:
        clauses.append("exists (select 1 from json_each(b.topics_json) where lower(value) = lower(?))")
        params.append(topic)
    where_sql = f"where {' and '.join(clauses)}" if clauses else ""
    params.append(match_query)
    params.append(limit)

    with get_connection() as connection:
        rows = connection.execute(
            f"""
            select
                b.*,
                bm25(bill_fts, 8.0, 6.0, 4.0, 1.5, 1.2, 1.2, 0.8, 1.0) as lexical_rank
            from bill_fts
            join bills b on b.bill_id = bill_fts.bill_id
            {where_sql}
              and bill_fts match ?
            order by lexical_rank asc
            limit ?
            """.replace("{where_sql}", where_sql if where_sql else "where 1 = 1"),
            tuple(params),
        ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        lexical_rank = float(row["lexical_rank"])
        score = 100.0 / (1.0 + max(0.0, lexical_rank))
        items.append(hydrate_bill(row, extra={"score": score}))
    return items


def list_candidates(limit: int = 80) -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            "select * from bills order by coalesce(latest_action_date, '1970-01-01') desc, identifier limit ?",
            (limit,),
        ).fetchall()
    return [hydrate_bill(row) for row in rows]


def list_bill_vectors() -> list[tuple[str, list[float]]]:
    with get_connection() as connection:
        rows = connection.execute("select bill_id, embedding_json from bill_vectors").fetchall()
    items: list[tuple[str, list[float]]] = []
    for row in rows:
        try:
            items.append((str(row["bill_id"]), json.loads(row["embedding_json"])))
        except json.JSONDecodeError:
            continue
    return items


def upsert_bill_vector(bill_id: str, vector: list[float]) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            insert into bill_vectors (bill_id, embedding_json)
            values (?, ?)
            on conflict(bill_id) do update set embedding_json = excluded.embedding_json
            """,
            (bill_id, json.dumps(vector)),
        )


def hydrate_bill(row: sqlite3.Row, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = dict(row)
    payload["topics"] = json.loads(payload.pop("topics_json"))
    if extra:
        payload.update(extra)
    return payload


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)
