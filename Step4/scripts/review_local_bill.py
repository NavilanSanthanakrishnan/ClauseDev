#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from step4.services.conflict_analysis import ConflictAnalysisService
from step4.services.bill_extraction import detect_file_type, extract_text_from_file
from step4.services.database import Database
from step4.services.testing_agent import TestingAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Step4 on a local bill file and ask the testing agent to review the result.")
    parser.add_argument("--file", required=True, help="Path to the local bill file (pdf/docx/txt).")
    parser.add_argument(
        "--expected",
        action="append",
        default=[],
        help="Expected conflict citation. May be passed multiple times.",
    )
    parser.add_argument(
        "--forbidden",
        action="append",
        default=[],
        help="Forbidden conflict citation. May be passed multiple times.",
    )
    parser.add_argument("--notes", default="", help="Short reviewer note or context.")
    parser.add_argument("--max-agent-attempts", type=int, default=5)
    args = parser.parse_args()

    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}")

    case = {
        "case_id": f"local-{file_path.stem}",
        "bill_identifier": file_path.name,
        "official_source_url": "",
        "expected_conflict_citations": args.expected,
        "forbidden_conflict_citations": args.forbidden,
        "notes": args.notes,
    }

    db = Database()
    db.open()
    try:
        service = ConflictAnalysisService(db)
        result = service.analyze(filename=file_path.name, payload=file_path.read_bytes())
    finally:
        db.close()
    bill_text = extract_text_from_file(detect_file_type(file_path.name), file_path.read_bytes())

    print("Step4 conflicts:")
    print(
        json.dumps(
            [
                {
                    "citation": finding.citation,
                    "finding_bucket": finding.finding_bucket,
                    "conflict_type": finding.conflict_type,
                    "confidence": finding.confidence,
                }
                for finding in result.conflicts
            ],
            indent=2,
        )
    )

    review = TestingAgent().review(
        case=case,
        bill_text=bill_text,
        result=result,
        max_attempts=args.max_agent_attempts,
    )
    print("\nTesting agent review:")
    print(json.dumps(review.__dict__, indent=2))


if __name__ == "__main__":
    main()
