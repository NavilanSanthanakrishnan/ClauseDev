#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = REPO_ROOT / "sql" / "bootstrap_legal_search.sql"
PSQL = "/opt/homebrew/opt/postgresql@17/bin/psql"


def main() -> None:
    if not SQL_PATH.is_file():
        raise SystemExit(f"Bootstrap SQL not found: {SQL_PATH}")

    command = [
        PSQL,
        "-h",
        "127.0.0.1",
        "-p",
        "55432",
        "-d",
        "postgres",
        "-f",
        str(SQL_PATH),
    ]
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
