#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from urllib import request


BASE_URL = "http://127.0.0.1:8001/api"


def get_json(path: str) -> dict:
    with request.urlopen(f"{BASE_URL}{path}") as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{BASE_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    health = get_json("/health")
    bill_stats = get_json("/stats")
    law_stats = get_json("/laws/stats")
    bill_search = post_json("/search/standard", {"query": "fluoride water tennessee", "filters": {"limit": 3}})
    law_search = post_json("/laws/search/standard", {"query": "wildfire risk laws", "filters": {"limit": 3}})
    law_agentic = post_json(
        "/laws/search/agentic",
        {"query": "Find California laws about labor retaliation", "filters": {"limit": 3}},
    )

    assert_true(health.get("status") == "ok", "Backend health endpoint failed.")
    assert_true(int(bill_stats.get("total_bills", 0)) > 0, "Bills database is empty.")
    assert_true(int(law_stats.get("total_laws", 0)) > 0, "Law database is empty.")
    assert_true(len(bill_search.get("items", [])) > 0, "Bill search returned no results.")
    assert_true(len(law_search.get("items", [])) > 0, "Law search returned no results.")
    assert_true(len(law_agentic.get("items", [])) > 0, "Agentic law search returned no results.")

    print("Smoke test passed", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        raise
