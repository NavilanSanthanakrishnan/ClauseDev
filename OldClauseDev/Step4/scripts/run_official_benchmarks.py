#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from step4.config import get_settings
from step4.services.conflict_analysis import ConflictAnalysisService
from step4.services.database import Database
from step4.services.testing_agent import TestingAgent


BENCHMARK_FILE = ROOT / "benchmarks" / "official_cases.json"
RESULTS_DIR = ROOT / "benchmarks" / "results"


def _normalize_citation(citation: str) -> str:
    return citation.strip().rstrip(".").upper()


def _load_cases(case_id: str | None) -> list[dict]:
    cases = json.loads(BENCHMARK_FILE.read_text())
    if case_id:
        cases = [case for case in cases if case["case_id"] == case_id]
    return cases


def _fetch_bill_case_text(case: dict) -> tuple[str, dict]:
    settings = get_settings()
    query = """
        WITH target AS (
            SELECT
                b.id,
                s.identifier AS session_identifier,
                b.identifier,
                b.title,
                b.latest_action_description
            FROM public.opencivicdata_bill b
            JOIN public.opencivicdata_legislativesession s
              ON s.id = b.legislative_session_id
            WHERE s.jurisdiction_id = 'ocd-jurisdiction/country:us/state:ca/government'
              AND s.identifier = %(session_identifier)s
              AND b.identifier = %(bill_identifier)s
        )
        SELECT
            target.session_identifier,
            target.identifier,
            target.title,
            target.latest_action_description,
            sb.raw_text
        FROM target
        JOIN public.opencivicdata_searchablebill sb
          ON sb.bill_id = target.id
        WHERE sb.raw_text IS NOT NULL
        ORDER BY length(sb.raw_text) DESC
        LIMIT 1
    """
    with psycopg.connect(settings.openstates_dsn, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "session_identifier": case["session_identifier"],
                    "bill_identifier": case["bill_identifier"],
                },
            )
            row = cursor.fetchone()
    if not row:
        raise RuntimeError(f"Could not find bill text for {case['case_id']}.")
    return row["raw_text"], {
        "session_identifier": row["session_identifier"],
        "bill_identifier": row["identifier"],
        "title": row["title"],
        "latest_action_description": row["latest_action_description"],
    }


def _expected_check(case: dict, result) -> dict:
    actual = {_normalize_citation(finding.citation) for finding in result.conflicts}
    expected = {_normalize_citation(citation) for citation in case.get("expected_conflict_citations", [])}
    forbidden = {_normalize_citation(citation) for citation in case.get("forbidden_conflict_citations", [])}
    missing = sorted(citation for citation in expected if citation not in actual)
    unexpected = sorted(citation for citation in actual if citation in forbidden)
    return {
        "passed": not missing and not unexpected,
        "missing_expected": missing,
        "forbidden_present": unexpected,
        "actual_conflicts": sorted(actual),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run official Step4 benchmarks against the local databases.")
    parser.add_argument("--case", help="Run a single benchmark case_id")
    parser.add_argument("--max-agent-attempts", type=int, default=10)
    parser.add_argument("--skip-agent", action="store_true")
    args = parser.parse_args()

    cases = _load_cases(args.case)
    if not cases:
        raise SystemExit("No benchmark cases found.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    db = Database()
    db.open()
    service = ConflictAnalysisService(db)
    testing_agent = TestingAgent()

    suite_results = []
    try:
        for case in cases:
            bill_text, official_metadata = _fetch_bill_case_text(case)
            result = service.analyze(
                filename=f"{case['session_identifier']}_{case['bill_identifier'].replace(' ', '_')}.txt",
                payload=bill_text.encode(),
            )
            expected_check = _expected_check(case, result)
            agent_review = None
            if not args.skip_agent:
                agent_review = testing_agent.review(
                    case=case,
                    bill_text=bill_text,
                    result=result,
                    max_attempts=args.max_agent_attempts,
                ).__dict__
                if (
                    agent_review["attempts_used"] >= args.max_agent_attempts
                    and agent_review["explanation"].startswith("Testing agent failed")
                ):
                    raise RuntimeError(
                        f"Testing agent failed more than {args.max_agent_attempts} times on {case['case_id']}: "
                        f"{agent_review['explanation']}"
                    )

            case_result = {
                "case": case,
                "official_metadata": official_metadata,
                "expected_check": expected_check,
                "agent_review": agent_review,
                "analysis": result.model_dump(),
            }
            suite_results.append(case_result)

            print(f"CASE {case['case_id']}")
            print(f"  expected_check.passed = {expected_check['passed']}")
            print(f"  actual_conflicts = {', '.join(expected_check['actual_conflicts']) or 'none'}")
            if expected_check["missing_expected"]:
                print(f"  missing_expected = {', '.join(expected_check['missing_expected'])}")
            if expected_check["forbidden_present"]:
                print(f"  forbidden_present = {', '.join(expected_check['forbidden_present'])}")
            if agent_review:
                print(f"  testing_agent.is_accurate = {agent_review['is_accurate']}")
                print(f"  testing_agent.explanation = {agent_review['explanation']}")

    finally:
        db.close()

    results_path = RESULTS_DIR / "latest.json"
    results_path.write_text(json.dumps(suite_results, indent=2))
    print(f"Wrote benchmark results to {results_path}")

    failed_cases = [
        item["case"]["case_id"]
        for item in suite_results
        if not item["expected_check"]["passed"] or (item["agent_review"] and not item["agent_review"]["is_accurate"])
    ]
    if failed_cases:
        raise SystemExit(f"Benchmark failures: {', '.join(failed_cases)}")


if __name__ == "__main__":
    main()
