#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the Step4 conflict-analysis API.")
    parser.add_argument("file", type=Path, help="Path to a PDF, DOCX, or TXT bill file")
    parser.add_argument("--url", default="http://127.0.0.1:8012/api/analyze")
    args = parser.parse_args()

    with args.file.open("rb") as handle:
        response = requests.post(args.url, files={"file": (args.file.name, handle)})
    response.raise_for_status()
    payload = response.json()

    profile = payload["profile"]
    print(f"Profile title: {profile['title']}")
    print(f"Origin: {profile['origin_country']} {profile['origin_state_code']}".strip())
    print(f"Candidate counts: {payload['candidate_counts']}")
    print(f"Conflicts returned: {len(payload['conflicts'])}")
    for idx, conflict in enumerate(payload["conflicts"][:8], start=1):
        print(f"{idx}. [{conflict['source_system']}] {conflict['citation']} confidence={conflict['confidence']}")
        print(f"   {conflict['explanation']}")


if __name__ == "__main__":
    main()
