from __future__ import annotations

from step4.services.legal_semantics import build_semantic_profile


def test_build_semantic_profile_tags_housing_disability_statute() -> None:
    profile = build_semantic_profile(
        citation="HSC 11834.23",
        heading="Local regulation of treatment facilities",
        hierarchy_path="ARTICLE 2. Local Regulation",
        body_text=(
            "An alcohol or other drug recovery or treatment facility that serves six or fewer persons "
            "shall be considered a residential use of property. A conditional use permit shall not be required."
        ),
    )

    assert "housing_land_use" in profile["domains"]
    assert "disability_civil_rights" in profile["domains"]
    assert any("shall" in item.lower() for item in profile["obligations"])
