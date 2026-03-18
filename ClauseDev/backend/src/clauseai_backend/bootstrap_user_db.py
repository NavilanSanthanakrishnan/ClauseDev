from sqlalchemy import text

from clauseai_backend.db.base import Base
from clauseai_backend.db.session import user_engine
from clauseai_backend.models import auth as _auth_models  # noqa: F401
from clauseai_backend.models import chat as _chat_models  # noqa: F401
from clauseai_backend.models import editor as _editor_models  # noqa: F401
from clauseai_backend.models import projects as _project_models  # noqa: F401
from clauseai_backend.models import workflow as _workflow_models  # noqa: F401


def ensure_user_db() -> None:
    with user_engine.begin() as connection:
        connection.execute(text("create schema if not exists auth"))
        connection.execute(text("create schema if not exists app"))
        connection.execute(text("create schema if not exists workflow"))
        connection.execute(text("create schema if not exists audit"))
        Base.metadata.create_all(bind=connection)


def main() -> None:
    ensure_user_db()
