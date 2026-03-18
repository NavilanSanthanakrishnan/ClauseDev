#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test the Step1 workflow upload API.")
    parser.add_argument("file", type=Path, help="Path to a PDF, DOCX, or TXT bill file")
    parser.add_argument("--url", default="http://127.0.0.1:8011/api/workflow/upload")
    args = parser.parse_args()

    with args.file.open("rb") as handle:
        response = requests.post(args.url, files={"file": (args.file.name, handle)})
    response.raise_for_status()
    payload = response.json()

    print(f"Session id: {payload['session_id']}")
    print(f"Stage: {payload['current_stage']}")
    print(f"Status: {payload['status']}")
    print(f"Draft length: {len(payload['current_draft_text'])}")
    print(f"Metadata status: {payload['metadata_status']}")
    print(f"Similarity status: {payload['similarity_status']}")


if __name__ == "__main__":
    main()
