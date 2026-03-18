from __future__ import annotations

from types import SimpleNamespace

from step4.models import LegalCandidate, UploadedBillProfile
from step4.services.legal_retrieval import LegalRetriever


def test_agentic_expand_adds_candidates_from_tool_actions() -> None:
    retriever = LegalRetriever.__new__(LegalRetriever)
    retriever.settings = SimpleNamespace(
        agentic_max_rounds=2,
        agentic_actions_per_round=3,
        agentic_action_limit=6,
    )
    retriever._plan_agentic_actions = lambda **_: {
        "stop": False,
        "reason": "Need a stronger process-law statute.",
        "actions": [
            {
                "tool": "citation_lookup",
                "source_system": "california",
                "citation": "HSC 18949.6",
                "limit": 3,
            }
        ],
    }
    retriever._lookup_citation = lambda **_: [
        {
            "document_id": "ca:hsc189496",
            "source_kind": "section",
            "citation": "HSC 18949.6.",
            "heading": "Procedure regulations",
            "hierarchy_path": "Building standards",
            "source_url": "https://example.test/hsc189496",
            "body_text": "The commission shall adopt regulations governing the procedure for adoption of building standards.",
            "rank": 1.0,
        }
    ]
    retriever._search_text = lambda **_: []
    retriever._search_overlay = lambda **_: []
    retriever._expand_references = lambda **_: []
    retriever._hierarchy_neighbors = lambda **_: []

    profile = UploadedBillProfile(title="AB 1245", summary="Building standards bill.")
    seed = [
        LegalCandidate(
            document_id="ca:prc25620",
            source_system="california",
            source_kind="section",
            citation="PRC 25620.",
            heading="Existing section",
            body_text="Existing text",
        )
    ]

    expanded = retriever._agentic_expand(profile, seed, source_system="california", jurisdiction="CA")

    assert {candidate.citation for candidate in expanded} == {"PRC 25620.", "HSC 18949.6."}


def test_building_standards_overlay_terms_are_available() -> None:
    retriever = LegalRetriever.__new__(LegalRetriever)
    profile = UploadedBillProfile(
        title="AB 1245",
        summary="California Building Standards Code EV charging requirements enforced by the Energy Commission.",
        policy_domains=["building standards", "electric vehicle charging infrastructure"],
    )

    overlays = retriever._risk_overlay_terms(profile)

    assert "building_standards_process" in overlays
    assert "california_fund_structure" in overlays


def test_building_standards_domain_hints_include_process_statutes() -> None:
    retriever = LegalRetriever.__new__(LegalRetriever)
    profile = UploadedBillProfile(
        title="AB 1245",
        summary="California Building Standards Code EV charging rules enforced by the Energy Commission with penalty deposits into the Clean Transportation Fund.",
    )

    hints = retriever._domain_hint_citations(profile, source_system="california")

    assert "PRC 25402" in hints
    assert "HSC 18949.6" in hints
    assert "GOV 16370" in hints
