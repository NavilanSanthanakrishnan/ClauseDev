#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the Step1 similar-bills API.")
    parser.add_argument("file", type=Path, help="Path to a PDF, DOCX, or TXT bill file")
    parser.add_argument("--url", default="http://127.0.0.1:8011/api/search")
    args = parser.parse_args()

    with args.file.open("rb") as handle:
        response = requests.post(args.url, files={"file": (args.file.name, handle)})
    response.raise_for_status()
    payload = response.json()

    print(f"Profile title: {payload['profile']['title']}")
    print(f"Results returned: {len(payload['results'])}")
    for idx, bill in enumerate(payload["results"][:5], start=1):
        print(f"{idx}. {bill['identifier']} | {bill['jurisdiction_name']} | score={bill['final_score']}")
        print(f"   {bill['match_reason']}")


if __name__ == "__main__":
    main()
