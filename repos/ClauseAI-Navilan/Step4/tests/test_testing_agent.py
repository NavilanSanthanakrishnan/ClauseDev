from __future__ import annotations

from step4.models import ConflictFinding, ConflictSearchResult, UploadedBillProfile
from step4.services.testing_agent import TestingAgent


def test_compact_result_limits_fields() -> None:
    result = ConflictSearchResult(
        filename="sample.txt",
        file_type="txt",
        extracted_text_preview="preview",
        extracted_text_length=123,
        profile=UploadedBillProfile(
            title="Sample bill",
            summary="Summary",
            origin_country="US",
            origin_state_code="CA",
            explicit_citations=["LAB 510"],
        ),
        conflicts=[
            ConflictFinding(
                candidate_id="california:lab510",
                source_system="california",
                source_kind="section",
                citation="LAB 510",
                finding_bucket="direct_amendment",
                conflict_type="state contradiction",
                severity="high",
                confidence=0.95,
                bill_excerpt="bill excerpt",
                statute_excerpt="statute excerpt",
                explanation="explanation",
                why_conflict="why",
            )
        ],
        candidate_counts={"california": 12, "federal": 12},
        warnings=["warning"],
        timings={"total": 1.23},
    )

    compact = TestingAgent()._compact_result(result)

    assert compact["filename"] == "sample.txt"
    assert compact["profile"]["title"] == "Sample bill"
    assert compact["conflicts"][0]["citation"] == "LAB 510"
    assert "timings" not in compact
