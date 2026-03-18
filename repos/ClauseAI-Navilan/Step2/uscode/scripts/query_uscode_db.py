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


def _print_stats(db_path: Path) -> None:
    stats = uscode_local_db.get_stats(db_path)
    for key in sorted(stats):
        print(f"{key}: {stats[key]}")


def _print_node(db_path: Path, *, identifier: str | None, citation: str | None, cornell_url: str | None) -> None:
    row = uscode_local_db.get_node(identifier=identifier, citation=citation, cornell_url=cornell_url, db_path=db_path)
    if row is None:
        print("No matching node found.")
        return

    print(f"citation: {row['citation']}")
    print(f"identifier: {row['identifier']}")
    print(f"kind: {row['kind']}")
    print(f"label: {row['label']}")
    if row["heading"]:
        print(f"heading: {row['heading']}")
    if row["cornell_url"]:
        print(f"cornell_url: {row['cornell_url']}")
    print(f"breadcrumb: {row['breadcrumb']}")
    print()
    if row["content_text"]:
        print(row["content_text"][:4000])
        if len(row["content_text"]) > 4000:
            print("\n[content truncated]")
    elif row["notes_text"]:
        print(row["notes_text"][:4000])
        if len(row["notes_text"]) > 4000:
            print("\n[notes truncated]")


def _print_children(db_path: Path, parent_identifier: str) -> None:
    rows = uscode_local_db.list_children(parent_identifier, db_path=db_path)
    if not rows:
        print("No children found.")
        return

    for index, row in enumerate(rows, start=1):
        heading = f" - {row['heading']}" if row["heading"] else ""
        print(f"{index}. {row['citation']}{heading}")
        print(f"   id: {row['identifier']}")
        if row["cornell_url"]:
            print(f"   cornell: {row['cornell_url']}")


def _print_search_results(rows: list, show_url: bool = False) -> None:
    if not rows:
        print("No matches found.")
        return

    for index, row in enumerate(rows, start=1):
        heading = f" - {row['heading']}" if row["heading"] else ""
        print(f"{index}. {row['citation']}{heading}")
        print(f"   id: {row['identifier']}")
        if show_url and row["cornell_url"]:
            print(f"   cornell: {row['cornell_url']}")
        snippet = row["match_snippet"] or ""
        if snippet:
            print(f"   match: {snippet}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect the local SQLite U.S. Code database.")
    parser.add_argument("--db", default=str(uscode_local_db.DEFAULT_DB_PATH), help="SQLite database path.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("stats", help="Show build metadata and row counts.")

    show_parser = subparsers.add_parser("show", help="Show one node by identifier, citation, or Cornell URL.")
    show_group = show_parser.add_mutually_exclusive_group(required=True)
    show_group.add_argument("--id", dest="identifier")
    show_group.add_argument("--citation")
    show_group.add_argument("--url", dest="cornell_url")

    children_parser = subparsers.add_parser("children", help="List child nodes for a parent identifier.")
    children_parser.add_argument("--id", dest="identifier", required=True)

    search_parser = subparsers.add_parser("search", help="Full-text search sections.")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)

    provision_parser = subparsers.add_parser("search-provisions", help="Full-text search subsection-level provisions.")
    provision_parser.add_argument("query")
    provision_parser.add_argument("--limit", type=int, default=10)

    args = parser.parse_args()
    db_path = Path(args.db)

    if args.command == "stats":
        _print_stats(db_path)
    elif args.command == "show":
        _print_node(
            db_path,
            identifier=args.identifier,
            citation=args.citation,
            cornell_url=args.cornell_url,
        )
    elif args.command == "children":
        _print_children(db_path, args.identifier)
    elif args.command == "search":
        _print_search_results(uscode_local_db.search_sections(args.query, limit=args.limit, db_path=db_path), show_url=True)
    elif args.command == "search-provisions":
        _print_search_results(uscode_local_db.search_provisions(args.query, limit=args.limit, db_path=db_path))


if __name__ == "__main__":
    main()
