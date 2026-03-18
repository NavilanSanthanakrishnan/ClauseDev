#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from clause_backend.repositories import bills  # noqa: E402
from clause_backend.services.bootstrap import ensure_database  # noqa: E402
from clause_backend.services.gemini import embed_text, gemini_available  # noqa: E402


def main() -> None:
    if not gemini_available():
        raise SystemExit("CLAUSE_GEMINI_API_KEY is missing. Add it to .env.clauseainaviprod first.")

    ensure_database()
    candidates = bills.list_candidates(limit=5000)
    for item in candidates:
        text = "\n".join(
            [
                item["identifier"],
                item["title"],
                item["summary"],
                item["full_text"],
                " ".join(item["topics"]),
            ]
        )
        vector = embed_text(text)
        if vector:
            bills.upsert_bill_vector(item["bill_id"], vector)
            print(f"Embedded {item['identifier']}", flush=True)


if __name__ == "__main__":
    main()

