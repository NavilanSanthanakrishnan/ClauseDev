from __future__ import annotations

import re
from collections import OrderedDict


DOMAIN_KEYWORDS = {
    "labor_employment": ("wage", "overtime", "meal period", "rest period", "employee", "employer", "workweek"),
    "housing_land_use": ("zoning", "dwelling", "housing", "land use", "single-family", "conditional use permit"),
    "disability_civil_rights": ("disability", "reasonable accommodation", "recovery", "treatment facility", "discrimination"),
    "health_safety": ("health", "safety", "facility", "fire safety", "treatment", "medical"),
    "child_welfare": ("foster child", "juvenile court", "child welfare", "regional center", "developmental disability"),
}

RISK_TAG_KEYWORDS = {
    "federal_preemption": ("preempt", "notwithstanding", "federal law", "u.s.c."),
    "fair_housing": ("fair housing", "dwelling", "single-family", "zoning"),
    "ada_section504": ("qualified individual with a disability", "section 504", "public entity"),
    "minimum_wage_floor": ("minimum wage", "hourly wage"),
    "overtime_floor": ("overtime", "40 hours", "workweek"),
}


def _match_keywords(text: str, mapping: dict[str, tuple[str, ...]]) -> list[str]:
    lowered = text.lower()
    tags = [label for label, keywords in mapping.items() if any(keyword in lowered for keyword in keywords)]
    return list(OrderedDict.fromkeys(tags))


def _extract_sentences(text: str, trigger_words: tuple[str, ...], limit: int = 8) -> list[str]:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.;:])\s+", normalized)
    selected: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(word in lowered for word in trigger_words):
            selected.append(sentence[:400])
        if len(selected) >= limit:
            break
    return selected


def _extract_thresholds(text: str) -> list[str]:
    values = re.findall(r"(?:\$?\s*\d+(?:\.\d+)?\s*(?:hours?|days?|weeks?|percent|%)?)", text or "", re.IGNORECASE)
    cleaned = []
    for value in values:
        normalized = re.sub(r"\s+", " ", value.strip())
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)
        if len(cleaned) >= 12:
            break
    return cleaned


def build_semantic_profile(*, citation: str, heading: str, body_text: str, hierarchy_path: str) -> dict:
    text = " ".join(part for part in [citation, heading, hierarchy_path, body_text] if part)
    domains = _match_keywords(text, DOMAIN_KEYWORDS)
    risk_tags = _match_keywords(text, RISK_TAG_KEYWORDS)
    obligations = _extract_sentences(text, ("shall", "must", "required", "may not", "shall not"))
    permissions = _extract_sentences(text, ("may", "authorized", "permitted"), limit=6)
    thresholds = _extract_thresholds(text)
    profile_text = "\n".join(
        part
        for part in [
            citation,
            heading,
            hierarchy_path,
            "domains: " + ", ".join(domains) if domains else "",
            "risk_tags: " + ", ".join(risk_tags) if risk_tags else "",
            "obligations: " + " | ".join(obligations[:4]) if obligations else "",
            "permissions: " + " | ".join(permissions[:3]) if permissions else "",
            "thresholds: " + ", ".join(thresholds[:8]) if thresholds else "",
        ]
        if part
    )
    return {
        "domains": domains,
        "risk_tags": risk_tags,
        "obligations": obligations,
        "permissions": permissions,
        "thresholds": thresholds,
        "profile_text": profile_text,
    }
