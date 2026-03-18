from __future__ import annotations

import json
import os
import time
from base64 import urlsafe_b64decode
from pathlib import Path
from typing import Any

import httpx

from clauseai_backend.core.config import settings

CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_OAUTH_TOKEN_URL = "https://auth.openai.com/oauth/token"
CODEX_REFRESH_SKEW_SECONDS = 120
CODEX_AUTH_CLAIMS_KEY = "https://api.openai.com/auth"


class CodexAuthError(RuntimeError):
    pass


def _resolve_auth_path(codex_home: Path) -> Path:
    return codex_home.expanduser() / "auth.json"


def _read_auth_payload(codex_home: Path) -> dict[str, Any]:
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


def _write_auth_payload(codex_home: Path, payload: dict[str, Any]) -> None:
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


def _extract_account_id(tokens: dict[str, Any]) -> str:
    explicit_account_id = str(tokens.get("account_id") or "").strip()
    if explicit_account_id:
        return explicit_account_id

    for token_key in ("access_token", "id_token"):
        claims = _decode_jwt_claims(tokens.get(token_key))
        auth_claims = claims.get(CODEX_AUTH_CLAIMS_KEY)
        if isinstance(auth_claims, dict):
            account_id = str(auth_claims.get("chatgpt_account_id") or auth_claims.get("account_id") or "").strip()
            if account_id:
                return account_id

        for claim_key in ("chatgpt_account_id", "account_id"):
            account_id = str(claims.get(claim_key) or "").strip()
            if account_id:
                return account_id
    return ""


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
    account_id = _extract_account_id(updated)
    if account_id:
        updated["account_id"] = account_id
    return updated


def resolve_codex_runtime_credentials() -> dict[str, Any]:
    payload = _read_auth_payload(settings.codex_home)
    auth_mode = str(payload.get("auth_mode") or "").strip().lower()
    if auth_mode and auth_mode != "chatgpt":
        raise CodexAuthError("ClauseAIProd requires ChatGPT Codex OAuth credentials. Run `codex login` first.")

    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexAuthError("Codex auth file is missing the tokens object.")

    access_token = str(tokens.get("access_token") or "").strip()
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    account_id = _extract_account_id(tokens)

    if not access_token:
        raise CodexAuthError("Codex auth file is missing access_token.")
    if not account_id:
        raise CodexAuthError("Codex auth file is missing account_id.")

    if _token_is_expiring(access_token, CODEX_REFRESH_SKEW_SECONDS):
        refreshed = _refresh_tokens(dict(tokens), settings.codex_refresh_timeout_seconds)
        payload["tokens"] = refreshed
        payload["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _write_auth_payload(settings.codex_home, payload)
        access_token = str(refreshed.get("access_token") or "").strip()
        refresh_token = str(refreshed.get("refresh_token") or refresh_token).strip()
        account_id = _extract_account_id(refreshed) or account_id

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "account_id": account_id,
        "auth_mode": payload.get("auth_mode"),
        "auth_path": str(_resolve_auth_path(settings.codex_home)),
    }


def codex_auth_available() -> bool:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return False
    try:
        resolve_codex_runtime_credentials()
    except CodexAuthError:
        return False
    return True
