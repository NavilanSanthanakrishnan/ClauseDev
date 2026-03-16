from __future__ import annotations

from dataclasses import dataclass

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from step4.config import Settings, get_settings


REQUIRED_CALIFORNIA_OBJECTS = [
    "idx_official_law_sections_search",
    "section_search",
]

REQUIRED_USCODE_OBJECTS = [
    "idx_step4_usc_sections_search",
    "idx_step4_usc_provisions_search",
    "step4_usc_section_search",
    "step4_usc_provision_search",
]


@dataclass
class QueryDatabase:
    name: str
    pool: ConnectionPool

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


class Database:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.california_pool = ConnectionPool(
            conninfo=self.settings.california_dsn,
            min_size=self.settings.postgres_min_pool_size,
            max_size=self.settings.postgres_max_pool_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
        self.uscode_pool = ConnectionPool(
            conninfo=self.settings.uscode_dsn,
            min_size=self.settings.postgres_min_pool_size,
            max_size=self.settings.postgres_max_pool_size,
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=False,
        )
        self.california = QueryDatabase("california", self.california_pool)
        self.uscode = QueryDatabase("uscode", self.uscode_pool)

    def open(self) -> None:
        self.california_pool.open(wait=True)
        self.uscode_pool.open(wait=True)

    def close(self) -> None:
        self.california_pool.close()
        self.uscode_pool.close()

    def missing_indexes(self) -> dict[str, list[str]]:
        california_rows = self.california.fetch_all(
            """
            SELECT indexname AS object_name
            FROM pg_indexes
            WHERE schemaname = 'public'
            UNION
            SELECT viewname AS object_name
            FROM pg_views
            WHERE schemaname = 'public'
            """
        )
        uscode_rows = self.uscode.fetch_all(
            """
            SELECT indexname AS object_name
            FROM pg_indexes
            WHERE schemaname = 'public'
            UNION
            SELECT viewname AS object_name
            FROM pg_views
            WHERE schemaname = 'public'
            """
        )
        california_seen = {row["object_name"] for row in california_rows}
        uscode_seen = {row["object_name"] for row in uscode_rows}
        return {
            "california": [name for name in REQUIRED_CALIFORNIA_OBJECTS if name not in california_seen],
            "uscode": [name for name in REQUIRED_USCODE_OBJECTS if name not in uscode_seen],
        }
