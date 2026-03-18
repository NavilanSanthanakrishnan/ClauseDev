from __future__ import annotations

from step4.services.bill_profile import _fallback_profile


def test_fallback_profile_infers_us_and_california_from_text() -> None:
    profile = _fallback_profile(
        "California Assembly Bill 123\nAn act to add Section 510 to the Labor Code in the State of California."
    )
    assert profile.origin_country == "US"
    assert profile.origin_state_code == "CA"
    assert profile.title.startswith("California Assembly Bill 123")
