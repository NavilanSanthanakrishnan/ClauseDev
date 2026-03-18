#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step1.services.database import Database


SAMPLE_QUERIES = [
    ("wildfire", "wildfire"),
    ("housing", "housing"),
    ("health", "health"),
]


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "samples"
    output_dir.mkdir(parents=True, exist_ok=True)

    db = Database()
    db.open()
    try:
        for filename, phrase in SAMPLE_QUERIES:
            row = db.fetch_one(
                """
                SELECT
                    b.identifier,
                    b.title,
                    sb.raw_text
                FROM public.opencivicdata_bill b
                JOIN public.opencivicdata_searchablebill sb
                  ON sb.bill_id = b.id
                WHERE 'bill' = ANY(b.classification)
                  AND sb.is_error = false
                  AND sb.search_vector @@ websearch_to_tsquery('english', %(phrase)s)
                ORDER BY b.latest_action_date DESC NULLS LAST
                LIMIT 1
                """,
                {"phrase": phrase},
            )
            if not row:
                print(f"No sample found for {phrase}")
                continue
            output_path = output_dir / f"{filename}.txt"
            output_path.write_text(row["raw_text"], encoding="utf-8")
            print(f"Wrote {output_path.name}: {row['identifier']} - {row['title']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
