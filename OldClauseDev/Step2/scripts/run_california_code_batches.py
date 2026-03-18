#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step4.california_code_ingest import CaliforniaCodeDatabaseBuilder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the California code ingest in small batches to avoid leginfo rate limiting."
    )
    parser.add_argument(
        "--source-dir",
        default=str(Path(__file__).resolve().parents[1] / "CaliforniaCodeData"),
        help="Directory containing the local CaliforniaCodeData scrape.",
    )
    parser.add_argument(
        "--db",
        default=str(Path(__file__).resolve().parents[1] / "data" / "california_code.db"),
        help="Output SQLite database path.",
    )
    parser.add_argument(
        "--only-code",
        default=None,
        help="Optional code abbreviation filter such as WIC or GOV.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="How many pending pages to fetch per batch.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent workers per batch.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=20.0,
        help="Cooldown between batches.",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Optional cap on batches for a single run.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the existing SQLite database before rebuilding from scratch.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    source_dir = Path(args.source_dir).expanduser().resolve()
    db_path = Path(args.db).expanduser().resolve()

    if not source_dir.exists():
        raise SystemExit(f"Source directory does not exist: {source_dir}")

    if args.rebuild and db_path.exists():
        db_path.unlink()

    builder = CaliforniaCodeDatabaseBuilder(source_dir=source_dir, db_path=db_path)
    try:
        metadata_stats = builder.load_toc_metadata(only_code=args.only_code)
        print("Loaded TOC metadata:", metadata_stats, flush=True)

        batch_number = 0
        while True:
            status_counts = builder.source_page_status_counts(only_code=args.only_code)
            pending_count = status_counts.get("pending", 0)
            if pending_count == 0:
                print("No pending pages remain.", flush=True)
                break

            if args.max_batches is not None and batch_number >= args.max_batches:
                print("Reached max batches.", flush=True)
                break

            batch_number += 1
            fetch_stats = builder.fetch_and_parse_pages(
                only_code=args.only_code,
                limit_pages=args.batch_size,
                workers=args.workers,
                refetch_failed=False,
            )
            print(
                f"Batch {batch_number}:",
                fetch_stats,
                "status_counts=",
                builder.source_page_status_counts(only_code=args.only_code),
                flush=True,
            )
            if fetch_stats["pages_seen"] == 0:
                break
            sleep(max(0.0, args.sleep_seconds))

        print("Final counts:", builder.counts(), flush=True)
        print("Final statuses:", builder.source_page_status_counts(only_code=args.only_code), flush=True)
        print(f"SQLite database ready at: {db_path}", flush=True)
    finally:
        builder.close()


if __name__ == "__main__":
    main()
