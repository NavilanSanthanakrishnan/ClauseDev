from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from clause_backend.core.config import settings


def configure_connection(connection: sqlite3.Connection) -> sqlite3.Connection:
    connection.row_factory = sqlite3.Row
    connection.execute("pragma journal_mode = wal;")
    connection.execute("pragma foreign_keys = on;")
    return connection


@contextmanager
def get_connection() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.database_path)
    try:
        yield configure_connection(connection)
        connection.commit()
    finally:
        connection.close()


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "select name from sqlite_master where type in ('table', 'view') and name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def execute_script(path: Path) -> None:
    with get_connection() as connection:
        connection.executescript(path.read_text())

