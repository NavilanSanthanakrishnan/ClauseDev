from __future__ import annotations

from step4.services.legal_index import alias_forms, extract_references, normalize_citation


def test_normalize_citation_handles_sections() -> None:
    assert normalize_citation("29 U.S.C.  §  207(a)") == "29 U.S.C. § 207(A)"
    assert normalize_citation("lab 510.") == "LAB 510"


def test_alias_forms_generate_punctuation_light_variants() -> None:
    aliases = set(alias_forms("29 U.S.C. § 207(a)"))
    assert "29 U.S.C. § 207(A)" in aliases
    assert "29 USC 207(A)" in aliases


def test_extract_references_finds_california_and_federal_citations() -> None:
    refs = extract_references(
        "This section does not supersede HSC 13143 or 13143.6 and must comply with 42 U.S.C. § 3604(f)."
    )

    normalized = {ref.normalized_referenced_citation for ref in refs}
    assert "HSC 13143" in normalized
    assert "42 U.S.C. § 3604(F)" in normalized
