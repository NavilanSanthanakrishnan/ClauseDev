from __future__ import annotations

from fastapi import Header, HTTPException

from clause_backend.core.config import settings
from clause_backend.repositories import app_state


def auth_config() -> dict[str, bool]:
    return {"enabled": settings.auth_enabled}


def login(email: str, password: str) -> dict[str, object]:
    user = app_state.get_user_by_email(email)
    if not user or user["password_hash"] != app_state.hash_password(password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = app_state.create_session(str(user["user_id"]))
    return {
        "token": token,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "display_name": user["display_name"],
        },
    }


def current_user(authorization: str | None = Header(default=None)) -> dict[str, object]:
    if not settings.auth_enabled:
        user = app_state.get_user_by_email(settings.auth_dummy_email)
        if not user:
            raise HTTPException(status_code=500, detail="Demo user is not initialized")
        return {
            "user_id": user["user_id"],
            "email": user["email"],
            "display_name": user["display_name"],
        }

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.removeprefix("Bearer ").strip()
    user = app_state.get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired")
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "display_name": user["display_name"],
    }


def logout(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        app_state.delete_session(token)
    return {"ok": True}
