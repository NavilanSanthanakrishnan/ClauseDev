from __future__ import annotations

import json
import time
from base64 import urlsafe_b64decode
from pathlib import Path
from typing import Any

import httpx


CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_REFRESH_SKEW_SECONDS = 120


class CodexAuthError(RuntimeError):
    pass


def _resolve_auth_path(codex_home: str) -> Path:
    return Path(codex_home).expanduser() / "auth.json"


def _read_auth_payload(codex_home: str) -> dict[str, Any]:
    auth_path = _resolve_auth_path(codex_home)
    if not auth_path.is_file():
        raise CodexAuthError(f"Codex auth file not found at {auth_path}. Run `codex login` first.")
    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise CodexAuthError(f"Failed to read Codex auth file at {auth_path}.") from exc
    if not isinstance(payload, dict):
        raise CodexAuthError("Codex auth payload is not a JSON object.")
    return payload


def _write_auth_payload(codex_home: str, payload: dict[str, Any]) -> None:
    auth_path = _resolve_auth_path(codex_home)
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _decode_jwt_claims(token: Any) -> dict[str, Any]:
    if not isinstance(token, str) or token.count(".") < 2:
        return {}
    try:
        body = token.split(".")[1]
        padded = body + "=" * (-len(body) % 4)
        raw = urlsafe_b64decode(padded.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _token_is_expiring(access_token: str, skew_seconds: int) -> bool:
    claims = _decode_jwt_claims(access_token)
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)):
        return False
    return float(exp) <= (time.time() + max(0, int(skew_seconds)))


def _refresh_tokens(tokens: dict[str, str], timeout_seconds: float) -> dict[str, str]:
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    if not refresh_token:
        raise CodexAuthError("Codex auth is missing refresh_token. Run `codex login` again.")

    timeout = httpx.Timeout(max(5.0, float(timeout_seconds)))
    with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
        response = client.post(
            CODEX_OAUTH_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CODEX_OAUTH_CLIENT_ID,
            },
        )

    if response.status_code != 200:
        detail = f"Codex token refresh failed with status {response.status_code}."
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = str(payload.get("error_description") or payload.get("message") or payload.get("error") or detail)
        except Exception:
            pass
        raise CodexAuthError(f"{detail} Run `codex login` again if needed.")

    try:
        payload = response.json()
    except Exception as exc:
        raise CodexAuthError("Codex token refresh returned invalid JSON.") from exc

    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise CodexAuthError("Codex refresh did not return an access_token.")

    updated = dict(tokens)
    updated["access_token"] = access_token
    next_refresh = str(payload.get("refresh_token") or "").strip()
    if next_refresh:
        updated["refresh_token"] = next_refresh
    return updated


def resolve_codex_runtime_credentials(
    *,
    codex_home: str,
    refresh_if_expiring: bool = True,
    refresh_timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    payload = _read_auth_payload(codex_home)
    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexAuthError("Codex auth file is missing the tokens object.")

    access_token = str(tokens.get("access_token") or "").strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    account_id = str(tokens.get("account_id") or "").strip()

    if not access_token:
        raise CodexAuthError("Codex auth file is missing access_token.")
    if not refresh_token:
        raise CodexAuthError("Codex auth file is missing refresh_token.")
    if not account_id:
        raise CodexAuthError("Codex auth file is missing account_id.")

    if refresh_if_expiring and _token_is_expiring(access_token, CODEX_REFRESH_SKEW_SECONDS):
        refreshed = _refresh_tokens(dict(tokens), refresh_timeout_seconds)
        payload["tokens"] = refreshed
        _write_auth_payload(codex_home, payload)
        access_token = str(refreshed.get("access_token") or "").strip()
        refresh_token = str(refreshed.get("refresh_token") or refresh_token).strip()
        account_id = str(refreshed.get("account_id") or account_id).strip()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "account_id": account_id,
        "auth_mode": payload.get("auth_mode"),
        "auth_path": str(_resolve_auth_path(codex_home)),
    }

