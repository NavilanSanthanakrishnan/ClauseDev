from __future__ import annotations

from step4.services.bill_profile import _extract_structural_citations


def test_extract_structural_citations_parses_amended_california_sections() -> None:
    text = """
    An act to amend Section 510 of, and to add Section 511.5 to, the Labor Code,
    and to amend Section 4642 of the Welfare and Institutions Code.
    """

    citations = _extract_structural_citations(text, verb_patterns=("amend",))

    assert "LAB 510" in citations
    assert "WIC 4642" in citations
    assert "LAB 511.5" not in citations


def test_extract_structural_citations_parses_repealed_sections() -> None:
    text = """
    An act to repeal Section 1191.5 of the Labor Code and repeal Section 10231.5 of the Government Code.
    """

    citations = _extract_structural_citations(text, verb_patterns=("repeal",))

    assert set(citations) == {"LAB 1191.5", "GOV 10231.5"}
