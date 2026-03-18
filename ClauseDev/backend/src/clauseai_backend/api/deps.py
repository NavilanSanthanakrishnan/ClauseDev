from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from clauseai_backend.bootstrap_user_db import ensure_user_db
from clauseai_backend.core.security import decode_access_token
from clauseai_backend.db.session import ReferenceDatabases, get_reference_db_session, get_user_db_session
from clauseai_backend.models.auth import User
from clauseai_backend.services.editor_runtime import EditorRuntimeManager

auth_scheme = HTTPBearer(auto_error=False)


def get_user_db() -> Generator[Session, None, None]:
    yield from get_user_db_session()


def get_reference_db() -> Generator[ReferenceDatabases, None, None]:
    yield from get_reference_db_session()


def get_editor_runtime(request: Request) -> EditorRuntimeManager:
    runtime = getattr(request.app.state, "editor_runtime", None)
    if runtime is None:
        ensure_user_db()
        runtime = EditorRuntimeManager()
        runtime.recover_stale_sessions()
        request.app.state.editor_runtime = runtime
    return runtime


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: Session = Depends(get_user_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token subject is missing")

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not available")
    return user
