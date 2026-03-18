#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from clause_backend.repositories.bills import replace_bills  # noqa: E402


DEFAULT_DSN = "postgresql:///openstates_public_compat?host=/Users/navilan/Documents/openstates-data-2026/pg-runtime&port=55432"


BASE_QUERY = """
    with abstracts as (
        select bill_id, string_agg(abstract, E'\n\n' order by id::text) as summary_text
        from public.opencivicdata_billabstract
        group by bill_id
    ),
    sponsors as (
        select
            bill_id,
            string_agg(name, ', ' order by "primary" desc, classification, id::text) as sponsor_names
        from public.opencivicdata_billsponsorship
        where coalesce(name, '') <> ''
        group by bill_id
    ),
    sources as (
        select distinct on (bill_id)
            bill_id,
            nullif(url, '') as source_url
        from public.opencivicdata_billsource
        where coalesce(url, '') <> ''
        order by bill_id, id::text desc
    )
    select
        b.id,
        b.identifier,
        j.name as jurisdiction,
        case
            when j.id like '%%/state:%%'
            then upper(split_part(split_part(j.id, '/state:', 2), '/', 1))
            else 'US'
        end as state_code,
        coalesce(s.name, s.identifier) as session_name,
        coalesce(b.latest_action_description, 'Unknown') as status_text,
        case
            when lower(coalesce(b.latest_action_description, '')) like '%%failed%%' then 'Failed'
            when lower(coalesce(b.latest_action_description, '')) like '%%signed%%' then 'Passed'
            when lower(coalesce(b.latest_action_description, '')) like '%%chapter%%' then 'Passed'
            else 'Active'
        end as outcome,
        coalesce(a.summary_text, b.title) as summary_text,
        coalesce(a.summary_text, b.title) as excerpt,
        b.title,
        coalesce(array_to_string(b.subject, ', '), '') as topics_text,
        coalesce(b.latest_action_date, '') as latest_action_date,
        coalesce(sp.sponsor_names, 'OpenStates Import') as sponsor,
        coalesce(src.source_url, null) as source_url
    from public.opencivicdata_bill b
    join public.opencivicdata_legislativesession s on s.id = b.legislative_session_id
    join public.opencivicdata_jurisdiction j on j.id = s.jurisdiction_id
    left join abstracts a on a.bill_id = b.id
    left join sponsors sp on sp.bill_id = b.id
    left join sources src on src.bill_id = b.id
    where 'bill' = any(b.classification)
"""


DETAIL_QUERY = (
    BASE_QUERY
    + """
  and b.id = any(%s::text[])
order by j.name, b.latest_action_date desc nulls last, b.identifier
"""
)


def recent_ids_query() -> str:
    return (
        """
    select b.id
    from public.opencivicdata_bill b
    where 'bill' = any(b.classification)
    order by b.updated_at desc, b.latest_action_date desc nulls last, b.identifier
    limit %s
"""
    )


def balanced_ids_query() -> str:
    return (
        """
    select b.id
    from public.opencivicdata_bill b
    join public.opencivicdata_legislativesession s on s.id = b.legislative_session_id
    where 'bill' = any(b.classification)
      and s.jurisdiction_id = %s
    order by b.updated_at desc, b.latest_action_date desc nulls last, b.identifier
    limit %s
"""
    )


def load_records(limit: int, dsn: str, mode: str) -> list[dict[str, object]]:
    bill_ids: list[str] = []
    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            if mode == "balanced":
                cursor.execute(
                    """
                    select distinct j.id
                    from public.opencivicdata_legislativesession s
                    join public.opencivicdata_jurisdiction j on j.id = s.jurisdiction_id
                    join public.opencivicdata_bill b on b.legislative_session_id = s.id
                    where 'bill' = any(b.classification)
                    order by j.id
                    """
                )
                jurisdiction_ids = [row[0] for row in cursor.fetchall()]
                query = balanced_ids_query()
                for jurisdiction_id in jurisdiction_ids:
                    cursor.execute(query, (jurisdiction_id, limit))
                    bill_ids.extend(str(row[0]) for row in cursor.fetchall())
            else:
                cursor.execute(recent_ids_query(), (limit,))
                bill_ids = [str(row[0]) for row in cursor.fetchall()]

            if not bill_ids:
                return []

            cursor.execute(DETAIL_QUERY, (bill_ids,))
            rows = cursor.fetchall()

    records: list[dict[str, object]] = []
    for row in rows:
        topics = [item.strip() for item in str(row[9]).split(",") if item.strip()]
        records.append(
            {
                "bill_id": row[0],
                "identifier": row[1],
                "jurisdiction": row[2],
                "state_code": row[3],
                "session_name": row[4],
                "status": row[5],
                "outcome": row[6],
                "sponsor": row[12],
                "committee": "Imported",
                "title": row[8],
                "summary": row[7],
                "excerpt": str(row[7])[:280],
                "full_text": str(row[7]),
                "source_url": row[13],
                "latest_action_date": row[11] or None,
                "topics": topics or ["imported"],
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a recent OpenStates subset into the Clause local search database.")
    parser.add_argument(
        "--mode",
        choices=("balanced", "recent"),
        default="balanced",
        help="Balanced imports spread coverage across jurisdictions; recent imports take the latest bills overall.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Bills per jurisdiction in balanced mode, or total bills in recent mode. Higher values improve recall but take longer to import.",
    )
    parser.add_argument("--dsn", default=os.getenv("CLAUSE_OPENSTATES_DSN", DEFAULT_DSN))
    parser.add_argument("--write-seed", action="store_true", help="Write imported records back into database/seed/bills.json as well.")
    args = parser.parse_args()

    records = load_records(args.limit, args.dsn, args.mode)
    replace_bills(records)
    print(f"Imported {len(records)} bills using {args.mode} mode", flush=True)

    if args.write_seed:
        seed_path = ROOT / "database" / "seed" / "bills.json"
        seed_path.write_text(json.dumps(records, indent=2))
        print(f"Wrote {seed_path}", flush=True)


if __name__ == "__main__":
    main()
