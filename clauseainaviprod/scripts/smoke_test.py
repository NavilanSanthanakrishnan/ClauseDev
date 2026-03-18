#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import request


BASE_URL = "http://127.0.0.1:8001/api"
ENV_PATH = Path(__file__).resolve().parents[2] / ".env.clauseainaviprod"


def load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def get_json(path: str, headers: dict[str, str] | None = None) -> dict:
    req = request.Request(f"{BASE_URL}{path}", headers=headers or {})
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    env = load_env_file()
    auth_enabled = env.get("CLAUSE_AUTH_ENABLED", "").lower() in {"1", "true", "yes", "on"}
    auth_headers: dict[str, str] = {}

    health = get_json("/health")
    auth_config = get_json("/auth/config")

    if auth_enabled and auth_config.get("enabled"):
        login = post_json(
            "/auth/login",
            {
                "email": env.get("CLAUSE_AUTH_DUMMY_EMAIL", "demo@clause.local"),
                "password": env.get("CLAUSE_AUTH_DUMMY_PASSWORD", "Passw0rd!Passw0rd!"),
            },
        )
        auth_headers = {"Authorization": f"Bearer {login['token']}"}
        current_user = get_json("/auth/me", auth_headers)
        assert_true(bool(current_user.get("email")), "Authenticated user lookup failed.")

    bill_stats = get_json("/stats", auth_headers)
    law_stats = get_json("/laws/stats", auth_headers)
    bill_search = post_json(
        "/search/standard",
        {"query": "fluoride water tennessee", "filters": {"limit": 3}},
        auth_headers,
    )
    law_search = post_json(
        "/laws/search/standard",
        {"query": "wildfire risk laws", "filters": {"limit": 3}},
        auth_headers,
    )
    law_agentic = post_json(
        "/laws/search/agentic",
        {"query": "Find California laws about labor retaliation", "filters": {"limit": 3}},
        auth_headers,
    )
    projects = get_json("/projects", auth_headers)

    assert_true(health.get("status") == "ok", "Backend health endpoint failed.")
    assert_true(int(bill_stats.get("total_bills", 0)) > 0, "Bills database is empty.")
    assert_true(int(law_stats.get("total_laws", 0)) > 0, "Law database is empty.")
    assert_true(len(bill_search.get("items", [])) > 0, "Bill search returned no results.")
    assert_true(len(law_search.get("items", [])) > 0, "Law search returned no results.")
    assert_true(len(law_agentic.get("items", [])) > 0, "Agentic law search returned no results.")
    assert_true(isinstance(projects, list) and len(projects) > 0, "Project workspace list returned no items.")

    print("Smoke test passed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise
