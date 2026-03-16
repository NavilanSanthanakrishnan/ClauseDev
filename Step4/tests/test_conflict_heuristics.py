from __future__ import annotations

from step4.models import BillClause, LegalCandidate, UploadedBillProfile
from step4.services.conflict_analysis import ConflictAnalysisService, ConflictFinding


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


def test_amendment_conflict_identifies_operable_california_section() -> None:
    service = ConflictAnalysisService.__new__(ConflictAnalysisService)
    profile = UploadedBillProfile(
        summary="A bill to amend Section 510 of the Labor Code to allow flexible work schedules without daily overtime.",
        amended_citations=["LAB 510"],
        key_clauses=[
            BillClause(
                label="flexible work schedule",
                effect="permission",
                text="An employer may implement a 10-hour workday within a 40-hour workweek without overtime compensation for those additional daily hours.",
            )
        ],
    )
    candidate = LegalCandidate(
        document_id="lab-510",
        source_system="california",
        source_kind="section",
        citation="LAB 510.",
        excerpt="Eight hours of labor constitutes a day's work. Any work in excess of eight hours in one workday shall be compensated at one and one-half times the regular rate of pay.",
    )

    findings = service._amendment_conflict_findings(
        source_system="california",
        profile=profile,
        candidates=[candidate],
    )

    assert findings
    assert findings[0].citation == "LAB 510."
    assert findings[0].conflict_type == "state contradiction"
    assert findings[0].finding_bucket == "direct_amendment"


def test_postprocess_drops_federal_207_for_agricultural_overtime_bill() -> None:
    service = ConflictAnalysisService.__new__(ConflictAnalysisService)
    profile = UploadedBillProfile(
        summary="Agricultural workers overtime compensation bill increasing the weekly threshold for an agricultural occupation.",
        key_clauses=[BillClause(label="ag overtime", effect="permission", text="Agricultural workers would receive overtime only after 48 hours in a workweek.")],
    )
    findings = [
        ConflictFinding(
            candidate_id="california:lab-860",
            source_system="california",
            source_kind="section",
            citation="LAB 860",
            conflict_type="state contradiction",
            severity="high",
            confidence=0.94,
            bill_excerpt="",
            statute_excerpt="",
            explanation="",
        ),
        ConflictFinding(
            candidate_id="federal:29usc207",
            source_system="federal",
            source_kind="section",
            citation="29 U.S.C. § 207",
            conflict_type="compliance impossibility",
            severity="high",
            confidence=0.81,
            bill_excerpt="",
            statute_excerpt="",
            explanation="",
        ),
    ]

    filtered = service._postprocess_findings(profile=profile, findings=findings)

    assert [finding.citation for finding in filtered] == ["LAB 860"]


def test_postprocess_drops_federal_207_for_daily_overtime_only_bill() -> None:
    service = ConflictAnalysisService.__new__(ConflictAnalysisService)
    profile = UploadedBillProfile(
        summary="Employment bill allowing workdays up to 10 hours per day within a 40-hour workweek without the obligation to pay overtime compensation for those additional hours in a workday.",
        key_clauses=[BillClause(label="flex schedule", effect="permission", text="An employee-selected flexible work schedule may provide for workdays up to 10 hours per day within a 40-hour workweek.")],
    )
    findings = [
        ConflictFinding(
            candidate_id="california:lab-510",
            source_system="california",
            source_kind="section",
            citation="LAB 510",
            conflict_type="state contradiction",
            severity="high",
            confidence=0.95,
            bill_excerpt="",
            statute_excerpt="",
            explanation="",
        ),
        ConflictFinding(
            candidate_id="federal:29usc207",
            source_system="federal",
            source_kind="section",
            citation="29 U.S.C. § 207",
            conflict_type="compliance impossibility",
            severity="high",
            confidence=0.8,
            bill_excerpt="",
            statute_excerpt="",
            explanation="",
        ),
    ]

    filtered = service._postprocess_findings(profile=profile, findings=findings)

    assert [finding.citation for finding in filtered] == ["LAB 510"]


def test_postprocess_relabels_civil_rights_federal_findings() -> None:
    service = ConflictAnalysisService.__new__(ConflictAnalysisService)
    profile = UploadedBillProfile(summary="Zoning rule affecting recovery homes and people with disabilities.")
    findings = [
        ConflictFinding(
            candidate_id="federal:ada",
            source_system="federal",
            source_kind="section",
            citation="42 U.S.C. § 12132",
            conflict_type="federal preemption",
            severity="medium",
            confidence=0.6,
            bill_excerpt="",
            statute_excerpt="",
            explanation="Potential disability discrimination exposure.",
        )
    ]

    filtered = service._postprocess_findings(profile=profile, findings=findings)

    assert filtered[0].finding_bucket == "civil_rights_risk"
