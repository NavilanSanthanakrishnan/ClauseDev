#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from step4.config import get_settings
from step4.services.legal_semantics import build_semantic_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Build precached semantic profiles for the canonical legal index.")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    with psycopg.connect(settings.legal_index_dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            if not args.resume:
                cursor.execute("TRUNCATE legal_semantic_profiles")
                connection.commit()

            where_clause = ""
            if args.resume:
                where_clause = """
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM legal_semantic_profiles p
                        WHERE p.document_id = d.document_id
                    )
                """

            cursor.execute(
                f"""
                SELECT d.document_id, d.citation, d.heading, d.hierarchy_path, d.body_text
                FROM legal_documents d
                {where_clause}
                ORDER BY d.document_id
                """
            )

            inserted = 0
            while True:
                rows = cursor.fetchmany(args.batch_size)
                if not rows:
                    break
                with connection.cursor() as write_cursor:
                    for row in rows:
                        profile = build_semantic_profile(
                            citation=row["citation"],
                            heading=row["heading"] or "",
                            hierarchy_path=row["hierarchy_path"] or "",
                            body_text=row["body_text"] or "",
                        )
                        write_cursor.execute(
                            """
                            INSERT INTO legal_semantic_profiles (
                                document_id, domains, risk_tags, obligations, permissions, thresholds, profile_text
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (document_id) DO UPDATE SET
                                domains = EXCLUDED.domains,
                                risk_tags = EXCLUDED.risk_tags,
                                obligations = EXCLUDED.obligations,
                                permissions = EXCLUDED.permissions,
                                thresholds = EXCLUDED.thresholds,
                                profile_text = EXCLUDED.profile_text
                            """,
                            (
                                row["document_id"],
                                json.dumps(profile["domains"]),
                                json.dumps(profile["risk_tags"]),
                                json.dumps(profile["obligations"]),
                                json.dumps(profile["permissions"]),
                                json.dumps(profile["thresholds"]),
                                profile["profile_text"],
                            ),
                        )
                inserted += len(rows)
                connection.commit()
                print(f"semantic profiles: processed {inserted}", flush=True)

        with connection.cursor() as cursor:
            count_row = cursor.execute("SELECT count(*) AS total FROM legal_semantic_profiles").fetchone()
            count = count_row["total"]
    print(f"Built legal_semantic_profiles rows: {count}")


if __name__ == "__main__":
    main()
