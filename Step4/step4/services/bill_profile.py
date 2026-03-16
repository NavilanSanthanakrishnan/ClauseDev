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


def _fallback_search_phrases(text: str) -> list[str]:
    normalized = re.sub(r"[^a-zA-Z0-9\\s]", " ", text.lower())
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
        explicit_citations=[],
        conflict_search_phrases=_fallback_search_phrases(summary_text),
        key_clauses=clauses,
    )


class BillProfileExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = CodexClient()

    def extract(self, bill_text: str) -> UploadedBillProfile:
        trimmed_bill_text = bill_text[: self.settings.max_bill_chars_for_llm]
        user_prompt = (
            "Profile this uploaded bill for contradiction search against California law and the U.S. Code.\n\n"
            "Return only the JSON object.\n\n"
            f"Bill text:\n{trimmed_bill_text}"
        )
        try:
            payload = self.client.chat_json(system_prompt=PROFILE_SYSTEM_PROMPT, user_prompt=user_prompt)
            return UploadedBillProfile.model_validate(payload)
        except Exception:
            return _fallback_profile(trimmed_bill_text)
