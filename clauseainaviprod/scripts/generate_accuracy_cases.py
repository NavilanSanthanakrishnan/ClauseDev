#!/usr/bin/env python3
from __future__ import annotations

import json
import random
import re
import sqlite3
from pathlib import Path

import psycopg

from clause_backend.core.config import settings


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT.parent / ".env.clauseainaviprod"
DATABASE_PATH = ROOT / "database" / "clause.sqlite3"
OUTPUT_PATH = ROOT / "artifacts" / "qa" / "accuracy_cases.json"
SEED = 20260318

STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "for",
    "with",
    "to",
    "of",
    "in",
    "on",
    "act",
    "bill",
    "section",
    "title",
    "chapter",
    "shall",
    "this",
    "that",
}


def load_env() -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        payload[key.strip()] = value.strip()
    return payload


def normalize_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 2]


def top_terms(text: str, count: int = 4) -> list[str]:
    terms: list[str] = []
    for token in normalize_tokens(text):
        if token not in terms:
            terms.append(token)
        if len(terms) >= count:
            break
    return terms


def bill_cases() -> list[dict[str, object]]:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        select bill_id, identifier, jurisdiction, title, summary
        from bills
        order by latest_action_date desc, identifier
        """
    ).fetchall()
    connection.close()

    records = [dict(row) for row in rows]
    random.Random(SEED).shuffle(records)
    identifier_counts: dict[str, int] = {}
    for record in records:
        identifier_counts[str(record["identifier"])] = identifier_counts.get(str(record["identifier"]), 0) + 1

    cases: list[dict[str, object]] = []
    for record in records[:150]:
        query = str(record["identifier"])
        if identifier_counts[query] > 1:
            query = f"{record['jurisdiction']} {query}"
        cases.append(
            {
                "kind": "bill-standard-identifier",
                "endpoint": "/search/standard",
                "query": query,
                "filters": {"limit": 5},
                "expected_id": record["bill_id"],
                "expected_rank_max": 1,
            }
        )

    for record in records[150:250]:
        terms = top_terms(f"{record['title']} {record['summary']}", 4)
        if not terms:
            continue
        cases.append(
            {
                "kind": "bill-standard-keywords",
                "endpoint": "/search/standard",
                "query": " ".join(terms),
                "filters": {"limit": 5},
                "expected_id": record["bill_id"],
                "expected_rank_max": 5,
            }
        )

    for record in records[25:125]:
        terms = top_terms(record["summary"], 4) or top_terms(record["title"], 4)
        if not terms:
            continue
        cases.append(
            {
                "kind": "bill-agentic-intent",
                "endpoint": "/search/agentic",
                "query": f"Find legislation in {record['jurisdiction']} about {' '.join(terms)}",
                "filters": {"limit": 8},
                "expected_id": record["bill_id"],
                "expected_rank_max": 8,
            }
        )

    return cases


def california_law_rows(dsn: str, limit: int) -> list[dict[str, object]]:
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    id,
                    law_code || ' ' || section_num as citation,
                    coalesce(content_text, '') as body_text
                from public.official_law_sections
                where coalesce(content_text, '') <> ''
                order by id
                limit %s
                """,
                (limit,),
            )
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def uscode_rows(dsn: str, limit: int) -> list[dict[str, object]]:
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    identifier,
                    citation,
                    coalesce(heading, '') as heading,
                    coalesce(full_text, content_text, '') as body_text
                from public.usc_nodes
                where kind = 'section'
                  and coalesce(full_text, content_text, '') <> ''
                order by identifier
                limit %s
                """,
                (limit,),
            )
            columns = [column.name for column in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def law_cases(env: dict[str, str]) -> list[dict[str, object]]:
    randomizer = random.Random(SEED)
    california = california_law_rows(env.get("CLAUSE_CALIFORNIA_CODE_DSN", settings.california_code_dsn), 220)
    federal = uscode_rows(env.get("CLAUSE_USCODE_DSN", settings.uscode_dsn), 180)
    randomizer.shuffle(california)
    randomizer.shuffle(federal)

    cases: list[dict[str, object]] = []

    for record in california[:80]:
        cases.append(
            {
                "kind": "law-standard-citation",
                "endpoint": "/laws/search/standard",
                "query": record["citation"],
                "filters": {"limit": 5},
                "expected_id": f"ca_code:{record['id']}",
                "expected_rank_max": 1,
            }
        )

    for record in federal[:70]:
        cases.append(
            {
                "kind": "law-standard-citation",
                "endpoint": "/laws/search/standard",
                "query": record["citation"],
                "filters": {"limit": 5},
                "expected_id": f"uscode:{record['identifier']}",
                "expected_rank_max": 1,
            }
        )

    for record in california[80:130]:
        terms = top_terms(record["body_text"], 4)
        if not terms:
            continue
        cases.append(
            {
                "kind": "law-agentic-intent",
                "endpoint": "/laws/search/agentic",
                "query": f"Find California laws about {' '.join(terms)}",
                "filters": {"limit": 8},
                "expected_id": f"ca_code:{record['id']}",
                "expected_rank_max": 8,
            }
        )

    for record in federal[70:120]:
        terms = top_terms(f"{record['heading']} {record['body_text']}", 4)
        if not terms:
            continue
        cases.append(
            {
                "kind": "law-agentic-intent",
                "endpoint": "/laws/search/agentic",
                "query": f"Find federal law about {' '.join(terms)}",
                "filters": {"limit": 8},
                "expected_id": f"uscode:{record['identifier']}",
                "expected_rank_max": 8,
            }
        )

    return cases


def main() -> None:
    env = load_env()
    cases = bill_cases() + law_cases(env)
    cases = cases[:500]
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"seed": SEED, "count": len(cases), "cases": cases}, indent=2), encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
