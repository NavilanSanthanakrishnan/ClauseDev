from fastapi import APIRouter
from sqlalchemy import text

from clauseai_backend.db.session import (
    california_code_engine,
    legal_index_engine,
    openstates_engine,
    uscode_engine,
    user_engine,
)

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    with user_engine.connect() as conn:
        conn.execute(text("select 1"))
    with openstates_engine.connect() as conn:
        conn.execute(text("select 1"))
    with california_code_engine.connect() as conn:
        conn.execute(text("select 1"))
    with legal_index_engine.connect() as conn:
        conn.execute(text("select 1"))
    with uscode_engine.connect() as conn:
        conn.execute(text("select 1"))
    return {
        "status": "ok",
        "user_db": "connected",
        "openstates_db": "connected",
        "california_code_db": "connected",
        "legal_index_db": "connected",
        "uscode_db": "connected",
    }
