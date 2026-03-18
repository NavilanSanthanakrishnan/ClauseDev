from __future__ import annotations

import re
from collections import Counter

from step4.config import get_settings
from step4.models import BillClause, UploadedBillProfile
from step4.services.codex_client import CodexClient


PROFILE_SYSTEM_PROMPT = """You are a legislative conflict-search profiler.

Return ONLY valid JSON.

Your job is to turn the uploaded bill into a structured profile optimized for finding conflicting statutes, not merely related statutes.

Expected JSON:
{
  "title": "",
  "summary": "",
  "origin_country": "",
  "origin_country_confidence": 0.0,
  "origin_state_code": "",
  "origin_state_confidence": 0.0,
  "bill_category": "",
  "policy_domains": [],
  "affected_entities": [],
  "required_actions": [],
  "prohibited_actions": [],
  "permissions_created": [],
  "enforcement_mechanisms": [],
  "named_agencies": [],
  "explicit_citations": [],
  "amended_citations": [],
  "repealed_citations": [],
  "conflict_search_phrases": [],
  "key_clauses": [
    {
      "label": "",
      "effect": "requirement|prohibition|permission|procedure|preemption|penalty",
      "text": ""
    }
  ]
}

Rules:
- Identify the country of origin from the bill text itself. Use "US" if the bill is clearly from the United States.
- `origin_state_code` should only be a 2-letter U.S. state code when it is explicit or very obvious.
- Focus on clauses that could contradict existing law: mandatory duties, prohibitions, permissions, timelines, penalties, exemptions, overrides, and preemption language.
- `explicit_citations` should normalize citations where possible, for example `LAB 510`, `29 U.S.C. § 207`, `WIC 4512`.
- `amended_citations` should list current statutes the bill expressly amends.
- `repealed_citations` should list current statutes the bill expressly repeals.
- `conflict_search_phrases` should be 10 to 16 short high-signal search anchors aimed at statutes that could block, override, or contradict the bill.
- `key_clauses` should contain the most conflict-relevant snippets from the bill, quoted faithfully but kept concise.
"""


STATE_NAME_TO_CODE = {
    "california": "CA",
    "new york": "NY",
    "texas": "TX",
    "florida": "FL",
    "washington": "WA",
}

CALIFORNIA_CODE_NAMES = {
    "Business and Professions Code": "BPC",
    "Civil Code": "CIV",
    "Code of Civil Procedure": "CCP",
    "Education Code": "EDC",
    "Elections Code": "ELEC",
    "Family Code": "FAM",
    "Food and Agricultural Code": "FAC",
    "Government Code": "GOV",
    "Health and Safety Code": "HSC",
    "Insurance Code": "INS",
    "Labor Code": "LAB",
    "Penal Code": "PEN",
    "Public Contract Code": "PCC",
    "Public Resources Code": "PRC",
    "Public Utilities Code": "PUC",
    "Revenue and Taxation Code": "RTC",
    "Unemployment Insurance Code": "UIC",
    "Vehicle Code": "VEH",
    "Welfare and Institutions Code": "WIC",
}


def _normalize_california_citation(code_abbrev: str, section_number: str) -> str:
    return f"{code_abbrev} {section_number.strip().rstrip('.')}"


def _split_section_numbers(raw: str) -> list[str]:
    cleaned = re.sub(r"\band\b", ",", raw, flags=re.IGNORECASE)
    cleaned = cleaned.replace("through", ",").replace("–", "-")
    parts = re.split(r"[,;]", cleaned)
    return [part.strip().rstrip(".") for part in parts if re.match(r"^[0-9A-Za-z.\-]+$", part.strip())]


def _extract_structural_citations(
    bill_text: str,
    *,
    verb_patterns: tuple[str, ...],
) -> list[str]:
    window = bill_text[:10000]
    citations: list[str] = []
    for code_name, code_abbrev in CALIFORNIA_CODE_NAMES.items():
        for match in re.finditer(re.escape(code_name), window, re.IGNORECASE):
            segment_start = max(
                window.rfind("Code", 0, match.start()),
                window.rfind("\n", 0, match.start()),
                window.rfind(";", 0, match.start()),
            )
            segment = window[segment_start + 1 : match.end()]
            lowered_segment = segment.lower()
            if not any(verb in lowered_segment for verb in verb_patterns):
                continue
            for section_match in re.finditer(r"Sections?\s+([0-9A-Za-z.,\sand\-]+)\s+of\b", segment, re.IGNORECASE):
                for section_number in _split_section_numbers(section_match.group(1)):
                    citations.append(_normalize_california_citation(code_abbrev, section_number))
    return list(dict.fromkeys(citations))


def _extract_explicit_uscode_citations(bill_text: str) -> list[str]:
    citations: list[str] = []
    for title, section in re.findall(r"(\d+)\s*U\.?S\.?C\.?\s*(?:§+)?\s*([0-9A-Za-z.\-()]+)", bill_text, re.IGNORECASE):
        citations.append(f"{title} U.S.C. § {section}")
    return list(dict.fromkeys(citations))


def _fallback_search_phrases(text: str) -> list[str]:
    normalized = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    tokens = [token for token in normalized.split() if len(token) > 4]
    counts = Counter(tokens)
    common = [word for word, _ in counts.most_common(14)]
    phrases = [" ".join(common[idx : idx + 3]).strip() for idx in range(0, min(len(common), 10), 2)]
    return [phrase for phrase in phrases if phrase]


def _fallback_profile(bill_text: str) -> UploadedBillProfile:
    lines = [line.strip() for line in bill_text.splitlines() if line.strip()]
    title = lines[0][:160] if lines else "Uploaded bill"
    summary_text = " ".join(lines[:24])[:1400]
    lowered = summary_text.lower()
    origin_country = "US" if any(term in lowered for term in ("california", "assembly bill", "senate bill", "u.s.", "united states")) else ""
    origin_state = ""
    for name, code in STATE_NAME_TO_CODE.items():
        if name in lowered:
            origin_state = code
            break
    clauses = []
    for line in lines[:12]:
        if any(keyword in line.lower() for keyword in ("shall", "may not", "must", "prohibit", "permit", "require")):
            clauses.append(BillClause(label="bill clause", effect="requirement", text=line[:260]))
        if len(clauses) >= 4:
            break
    return UploadedBillProfile(
        title=title,
        summary=summary_text,
        origin_country=origin_country,
        origin_country_confidence=0.55 if origin_country else 0.0,
        origin_state_code=origin_state,
        origin_state_confidence=0.55 if origin_state else 0.0,
        bill_category="",
        policy_domains=[],
        affected_entities=[],
        required_actions=[],
        prohibited_actions=[],
        permissions_created=[],
        enforcement_mechanisms=[],
        named_agencies=[],
        explicit_citations=_extract_explicit_uscode_citations(summary_text),
        amended_citations=_extract_structural_citations(summary_text, verb_patterns=("amend",)),
        repealed_citations=_extract_structural_citations(summary_text, verb_patterns=("repeal",)),
        conflict_search_phrases=_fallback_search_phrases(summary_text),
        key_clauses=clauses,
    )


class BillProfileExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = CodexClient()

    def extract(self, bill_text: str) -> UploadedBillProfile:
        trimmed_bill_text = bill_text[: self.settings.max_bill_chars_for_llm]
        amended_citations = _extract_structural_citations(trimmed_bill_text, verb_patterns=("amend",))
        repealed_citations = _extract_structural_citations(trimmed_bill_text, verb_patterns=("repeal",))
        explicit_uscode_citations = _extract_explicit_uscode_citations(trimmed_bill_text)
        user_prompt = (
            "Profile this uploaded bill for contradiction search against California law and the U.S. Code.\n\n"
            "Return only the JSON object.\n\n"
            f"Bill text:\n{trimmed_bill_text}"
        )
        try:
            payload = self.client.chat_json(system_prompt=PROFILE_SYSTEM_PROMPT, user_prompt=user_prompt)
            profile = UploadedBillProfile.model_validate(payload)
        except Exception:
            profile = _fallback_profile(trimmed_bill_text)

        explicit_citations = list(
            dict.fromkeys(
                [
                    *profile.explicit_citations,
                    *explicit_uscode_citations,
                    *amended_citations,
                    *repealed_citations,
                ]
            )
        )
        return profile.model_copy(
            update={
                "explicit_citations": explicit_citations,
                "amended_citations": list(dict.fromkeys([*profile.amended_citations, *amended_citations])),
                "repealed_citations": list(dict.fromkeys([*profile.repealed_citations, *repealed_citations])),
            }
        )
