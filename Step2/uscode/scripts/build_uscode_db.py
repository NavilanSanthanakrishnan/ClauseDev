#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

USCODE_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = USCODE_ROOT / "uscode_local_db.py"
SPEC = importlib.util.spec_from_file_location("uscode_local_db", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load module from {MODULE_PATH}")
uscode_local_db = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = uscode_local_db
SPEC.loader.exec_module(uscode_local_db)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a local SQLite U.S. Code database from the official OLRC XML archive."
    )
    parser.add_argument("--db", default=str(uscode_local_db.DEFAULT_DB_PATH), help="SQLite database path.")
    parser.add_argument("--archive", default=str(uscode_local_db.DEFAULT_ARCHIVE_PATH), help="Downloaded XML archive path.")
    parser.add_argument("--archive-url", help="Override the OLRC archive URL.")
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append/update without clearing existing rows first.",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Redownload the source archive even if it already exists locally.",
    )
    parser.add_argument(
        "--titles",
        nargs="*",
        help="Optional title filters, for example: 1 26 5a 50a.",
    )
    parser.add_argument(
        "--limit-titles",
        type=int,
        help="Import only the first N title files after filtering.",
    )
    args = parser.parse_args()

    release = uscode_local_db.discover_latest_release() if not args.archive_url else None
    if release is not None:
        print(f"Source release: {release.release_label}")
        print(f"Archive URL: {release.archive_url}")
    elif args.archive_url:
        print(f"Archive URL: {args.archive_url}")

    stats = uscode_local_db.build_uscode_database(
        db_path=Path(args.db),
        archive_path=Path(args.archive),
        archive_url=args.archive_url,
        reset=not args.append,
        force_download=args.force_download,
        titles=args.titles,
        limit_titles=args.limit_titles,
    )

    print()
    print(f"Database: {args.db}")
    print(f"Archive: {args.archive}")
    print(f"Title files imported: {stats.title_files}")
    print(f"Nodes imported: {stats.nodes}")
    print(f"Sections imported: {stats.sections}")
    print(f"Provisions imported: {stats.provisions}")
    print(f"References imported: {stats.references}")


if __name__ == "__main__":
    main()
