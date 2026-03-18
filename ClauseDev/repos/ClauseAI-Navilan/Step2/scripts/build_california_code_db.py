#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step4.california_code_ingest import CaliforniaCodeDatabaseBuilder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a California code SQLite database from local TOC JSON and official leginfo pages.")
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
        "--limit-pages",
        type=int,
        default=None,
        help="Optional limit on the number of official text pages to fetch in this run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of concurrent fetch workers for official pages.",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Load TOC metadata only and skip official page fetches.",
    )
    parser.add_argument(
        "--refetch-failed",
        action="store_true",
        help="Retry pages previously marked as failed.",
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
        print("Loaded TOC metadata:", metadata_stats)

        if args.metadata_only:
            print("Database counts:", builder.counts())
            return

        fetch_stats = builder.fetch_and_parse_pages(
            only_code=args.only_code,
            limit_pages=args.limit_pages,
            workers=args.workers,
            refetch_failed=args.refetch_failed,
        )
        print("Fetch/parse stats:", fetch_stats)
        print("Database counts:", builder.counts())
        print(f"SQLite database ready at: {db_path}")
    finally:
        builder.close()


if __name__ == "__main__":
    main()
