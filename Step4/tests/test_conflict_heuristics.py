from __future__ import annotations

from step4.models import BillClause, LegalCandidate, UploadedBillProfile
from step4.services.conflict_analysis import ConflictAnalysisService


def test_overtime_heuristic_identifies_california_threshold_conflict() -> None:
    service = ConflictAnalysisService.__new__(ConflictAnalysisService)
    profile = UploadedBillProfile(
        summary="California bill allowing 14-hour days and 80-hour weeks without overtime compensation.",
        permissions_created=["Employers may require employees to work 80 hours in a workweek without overtime compensation."],
        key_clauses=[BillClause(label="overtime", effect="permission", text="No overtime compensation is required for hours over 40 in a workweek.")],
    )
    candidate = LegalCandidate(
        document_id="lab-510",
        source_system="california",
        source_kind="section",
        citation="LAB 510.",
        excerpt="Eight hours of labor constitutes a day's work. Any work in excess of eight hours in one workday and any work in excess of 40 hours in any one workweek shall be compensated at one and one-half times the regular rate of pay.",
    )

    findings = service._heuristic_pattern_findings(
        source_system="california",
        profile=profile,
        candidates=[candidate],
    )

    assert findings
    assert findings[0].citation == "LAB 510."


def test_minimum_wage_heuristic_prefers_federal_savings_clause() -> None:
    service = ConflictAnalysisService.__new__(ConflictAnalysisService)
    profile = UploadedBillProfile(
        summary="California bill authorizing a $7.50 wage and barring any state or local agency from requiring a higher hourly minimum wage.",
        permissions_created=["No state or local agency shall require a higher hourly minimum wage."],
        key_clauses=[BillClause(label="minimum wage", effect="permission", text="Employers may pay $7.50 per hour notwithstanding any other law.")],
    )
    candidate = LegalCandidate(
        document_id="29usc218",
        source_system="federal",
        source_kind="section",
        citation="29 U.S.C. § 218",
        excerpt="No provision of this chapter shall excuse noncompliance with any Federal or State law or municipal ordinance establishing a minimum wage higher than the minimum wage established under this chapter.",
    )

    findings = service._heuristic_pattern_findings(
        source_system="federal",
        profile=profile,
        candidates=[candidate],
    )

    assert findings
    assert findings[0].citation == "29 U.S.C. § 218"
