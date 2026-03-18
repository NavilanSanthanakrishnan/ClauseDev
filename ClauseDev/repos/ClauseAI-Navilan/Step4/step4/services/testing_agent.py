from __future__ import annotations

import json
from dataclasses import dataclass

from step4.models import ConflictSearchResult
from step4.services.codex_client import CodexClient


TESTING_AGENT_PROMPT = """You are the Step4 testing agent.

Return ONLY valid JSON.

You are reviewing whether a bill-to-law conflict finder correctly identified conflicting statutes.

Expected JSON:
{
  "is_accurate": true,
  "missed_conflicts": [],
  "false_positives": [],
  "explanation": "",
  "improvement_suggestions": []
}

Rules:
- Judge the result against the bill text, the returned conflicts, and the benchmark expectations.
- Treat an expected citation as satisfied when the returned citation is the same section family, ignoring a trailing period.
- Mark `is_accurate` false if an expected conflict is missing or an obviously unrelated false positive is present.
- Keep `improvement_suggestions` concrete and short.
"""


@dataclass
class TestingAgentResult:
    is_accurate: bool
    missed_conflicts: list[str]
    false_positives: list[str]
    explanation: str
    improvement_suggestions: list[str]
    attempts_used: int


class TestingAgent:
    __test__ = False

    def __init__(self) -> None:
        self.client = CodexClient()

    def review(
        self,
        *,
        case: dict,
        bill_text: str,
        result: ConflictSearchResult,
        max_attempts: int = 3,
    ) -> TestingAgentResult:
        compact_result = self._compact_result(result)
        last_error = "No response."
        for attempt in range(1, max_attempts + 1):
            try:
                payload = self.client.chat_json(
                    system_prompt=TESTING_AGENT_PROMPT,
                    user_prompt=(
                        f"Benchmark case:\n{json.dumps(case, indent=2)}\n\n"
                        f"Bill text excerpt:\n{bill_text[:6000]}\n\n"
                        f"Step4 result:\n{json.dumps(compact_result, indent=2)}"
                    ),
                )
                return TestingAgentResult(
                    is_accurate=bool(payload.get("is_accurate")),
                    missed_conflicts=[str(item) for item in payload.get("missed_conflicts", [])],
                    false_positives=[str(item) for item in payload.get("false_positives", [])],
                    explanation=str(payload.get("explanation", "")),
                    improvement_suggestions=[str(item) for item in payload.get("improvement_suggestions", [])],
                    attempts_used=attempt,
                )
            except Exception as exc:
                last_error = str(exc)
        return TestingAgentResult(
            is_accurate=False,
            missed_conflicts=[],
            false_positives=[],
            explanation=f"Testing agent failed after {max_attempts} attempts: {last_error}",
            improvement_suggestions=["Inspect Codex response formatting or lower benchmark batch size."],
            attempts_used=max_attempts,
        )

    def _compact_result(self, result: ConflictSearchResult) -> dict:
        return {
            "filename": result.filename,
            "profile": {
                "title": result.profile.title,
                "summary": result.profile.summary,
                "origin_country": result.profile.origin_country,
                "origin_state_code": result.profile.origin_state_code,
                "policy_domains": result.profile.policy_domains[:8],
                "explicit_citations": result.profile.explicit_citations[:12],
                "amended_citations": result.profile.amended_citations[:12],
                "repealed_citations": result.profile.repealed_citations[:12],
                "key_clauses": [clause.model_dump() for clause in result.profile.key_clauses[:8]],
            },
            "candidate_counts": result.candidate_counts,
            "warnings": result.warnings,
            "conflicts": [
                {
                    "citation": finding.citation,
                    "source_system": finding.source_system,
                    "finding_bucket": finding.finding_bucket,
                    "conflict_type": finding.conflict_type,
                    "severity": finding.severity,
                    "confidence": finding.confidence,
                    "heading": finding.heading,
                    "hierarchy_path": finding.hierarchy_path,
                    "bill_excerpt": finding.bill_excerpt[:700],
                    "statute_excerpt": finding.statute_excerpt[:700],
                    "explanation": finding.explanation[:700],
                    "why_conflict": finding.why_conflict[:400],
                }
                for finding in result.conflicts[:12]
            ],
        }
