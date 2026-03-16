from __future__ import annotations

from pathlib import Path

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from step1.config import Settings, get_settings


REQUIRED_INDEXES = [
    "idx_step1_bill_id",
    "idx_step1_bill_legislative_session_id",
    "idx_step1_bill_classification_gin",
    "idx_step1_searchablebill_search_vector",
    "idx_step1_searchablebill_bill_id",
    "idx_step1_bill_search_docs_bill_id",
    "idx_step1_bill_search_docs_search_vector",
    "idx_step1_bill_search_docs_state_code",
    "idx_step1_bill_search_docs_jurisdiction_id",
    "idx_step1_legislativesession_id",
    "idx_step1_legislativesession_jurisdiction_id",
    "idx_step1_jurisdiction_id",
    "idx_step1_billsource_bill_id",
    "idx_step1_voteevent_bill_id",
]


class Database:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.pool = ConnectionPool(
            conninfo=self.settings.postgres_dsn,
            min_size=self.settings.postgres_min_pool_size,
            max_size=self.settings.postgres_max_pool_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )

    def open(self) -> None:
        self.pool.open(wait=True)

    def close(self) -> None:
        self.pool.close()

    def fetch_all(self, query: str, params: dict | tuple | None = None) -> list[dict]:
        with self.pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or {})
                return list(cursor.fetchall())

    def fetch_one(self, query: str, params: dict | tuple | None = None) -> dict | None:
        rows = self.fetch_all(query, params)
        return rows[0] if rows else None

    def execute(self, query: str, params: dict | tuple | None = None) -> None:
        with self.pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or {})

    def missing_indexes(self) -> list[str]:
        rows = self.fetch_all(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
               OR schemaname = 'step1'
            """
        )
        seen = {row["indexname"] for row in rows}
        return [name for name in REQUIRED_INDEXES if name not in seen]


def bootstrap_sql_path() -> Path:
    return Path(__file__).resolve().parents[2] / "sql" / "bootstrap_openstates_step1.sql"
