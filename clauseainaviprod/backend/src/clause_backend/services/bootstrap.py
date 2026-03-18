from __future__ import annotations

import json

from clause_backend.core.config import settings
from clause_backend.db import execute_script, get_connection, table_exists
from clause_backend.repositories.bills import replace_bills


def ensure_database() -> None:
    with get_connection() as connection:
        if not table_exists(connection, "bills") or not table_exists(connection, "bill_fts"):
            execute_script(settings.schema_path)

        row = connection.execute("select count(*) from bills").fetchone()
        count = int(row[0]) if row else 0

    if count == 0:
        records = json.loads(settings.seed_path.read_text())
        replace_bills(records)

