from __future__ import annotations

from types import SimpleNamespace

from step4.models import UploadedBillProfile
from step4.services.california_drafting import CaliforniaDraftingChecker


class _StubCalifornia:
    def __init__(self) -> None:
        self.sections = {
            "PRC 25620.": {
                "citation": "PRC 25620.",
                "section_number": "25620.",
                "hierarchy_path": "DIVISION 15 > CHAPTER 7.1 [25620. - 25620.15.]",
                "display_url": "https://example.test/prc25620",
                "body_text": "Existing PRC 25620 text.",
            },
            "PRC 25402.1.": {
                "citation": "PRC 25402.1.",
                "section_number": "25402.1.",
                "hierarchy_path": "DIVISION 15 > CHAPTER 5",
                "display_url": "https://example.test/prc254021",
                "body_text": "Local building departments shall enforce the standards.",
            },
            "PRC 25402.11.": {
                "citation": "PRC 25402.11.",
                "section_number": "25402.11.",
                "hierarchy_path": "DIVISION 15 > CHAPTER 5",
                "display_url": "https://example.test/prc2540211",
                "body_text": "The commission may adopt administrative enforcement regulations with penalties up to $2,500.",
            },
            "GOV 11343.4.": {
                "citation": "GOV 11343.4.",
                "section_number": "11343.4.",
                "hierarchy_path": "GOV rulemaking",
                "display_url": "https://example.test/gov113434",
                "body_text": "A regulation becomes effective on a quarterly basis after filing.",
            },
            "HSC 18930.": {
                "citation": "HSC 18930.",
                "section_number": "18930.",
                "hierarchy_path": "Building standards commission",
                "display_url": "https://example.test/hsc18930",
                "body_text": "Any building standard adopted by state agencies shall be submitted to and approved by the commission prior to codification.",
            },
            "HSC 18938.5.": {
                "citation": "HSC 18938.5.",
                "section_number": "18938.5.",
                "hierarchy_path": "Building permit applicability",
                "display_url": "https://example.test/hsc189385",
                "body_text": "Building standards apply based on the standards effective when the permit application is submitted.",
            },
        }
        self.chapter_anchors = {
            ("PRC", "15.", "8.6."): {
                "citation": "PRC 25740.",
                "section_number": "25740.",
                "hierarchy_path": "DIVISION 15 > CHAPTER 8.6 [25740. - 25751.]",
                "display_url": "https://example.test/prc25740",
            }
        }

    def fetch_one(self, query: str, params: dict | None = None) -> dict | None:
        params = params or {}
        if "citation" in params:
            return self.sections.get(params["citation"])
        key = (params["code_abbrev"], params["division"], params["chapter_num"])
        return self.chapter_anchors.get(key)


def _checker() -> CaliforniaDraftingChecker:
    return CaliforniaDraftingChecker(SimpleNamespace(california=_StubCalifornia()))


def test_detects_section_collision_and_chapter_range_mismatch() -> None:
    checker = _checker()
    profile = UploadedBillProfile(origin_state_code="CA")
    bill_text = (
        "An act to add Article 4.5 (commencing with Section 25620) to Chapter 8.6 of Division 15 "
        "of the Public Resources Code."
    )

    findings = checker.find_issues(profile=profile, bill_text=bill_text)
    citations = {finding.citation: finding for finding in findings}

    assert "PRC 25620." in citations
    assert citations["PRC 25620."].finding_bucket == "codification_conflict"
    assert citations["PRC 25620."].conflict_type == "same_section_number_reused_for different statutory text"
    assert "PRC 25740." in citations
    assert citations["PRC 25740."].conflict_type == "chapter range mismatch"


def test_detects_building_standards_timing_constraints() -> None:
    checker = _checker()
    profile = UploadedBillProfile(
        origin_state_code="CA",
        summary="EV charging bill.",
    )
    bill_text = (
        "This article shall take effect immediately upon passage. "
        "The California Energy Commission shall adopt implementing regulations within 90 days of enactment. "
        "These requirements shall be incorporated into the California Building Standards Code for electric vehicle charging."
    )

    findings = checker.find_issues(profile=profile, bill_text=bill_text)
    citations = {finding.citation for finding in findings}

    assert "GOV 11343.4." in citations
    assert "HSC 18930." in citations
    assert "HSC 18938.5." in citations


def test_detects_enforcement_and_penalty_overlap() -> None:
    checker = _checker()
    profile = UploadedBillProfile(origin_state_code="CA", summary="EV charger enforcement bill.")
    bill_text = (
        "The California Energy Commission shall enforce the provisions of this article. "
        "A civil penalty of $5,000 shall apply for each missing charger and $1,000 per day thereafter."
    )

    findings = checker.find_issues(profile=profile, bill_text=bill_text)
    citations = {finding.citation for finding in findings}

    assert "PRC 25402.1." in citations
    assert "PRC 25402.11." in citations
