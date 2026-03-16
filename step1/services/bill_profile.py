from __future__ import annotations

import re
from collections import Counter

from step1.config import get_settings
from step1.models import UploadedBillProfile
from step1.services.codex_client import CodexClient


PROFILE_SYSTEM_PROMPT = """You are a legislative bill semantic profiler.

Return ONLY valid JSON.

Your goal is to describe the bill in a way that helps retrieve similar bills by meaning, intent, policy mechanism, and affected entities, not by superficial word overlap.

Expected JSON:
{
  "title": "",
  "description": "",
  "summary": "",
  "policy_domain": [],
  "policy_intent": "",
  "legal_mechanisms": [],
  "affected_entities": [],
  "enforcement_mechanisms": [],
  "fiscal_elements": [],
  "bill_type_hints": [],
  "jurisdiction_hints": [],
  "search_phrases": []
}

Rules:
- `title`, `description`, and `summary` must be concise and faithful to the bill.
- `policy_domain` should contain 3 to 8 broad domains.
- `legal_mechanisms` should contain concrete mechanisms like reporting requirements, licensing, appropriations, penalties, mandates, disclosures, preemption, liability, procurement rules, tax credits.
- `affected_entities` should name who the bill regulates or benefits.
- `enforcement_mechanisms` should focus on agencies, penalties, compliance checks, audits, civil actions, or reporting oversight.
- `bill_type_hints` can include categories like budget, criminal, tax, labor, education, housing, health, environment, procurement, elections.
- `jurisdiction_hints` should only include explicit state abbreviations or `US` when obvious from the text. Leave empty if unclear.
- `search_phrases` should be 10 to 16 diverse search strings that capture topic, mechanism, and intent.
- At least half of `search_phrases` must be compact high-signal anchors of roughly 2 to 5 words, such as program names, statutory act names, agency names, regulated entities, or mechanism phrases.
- The remaining `search_phrases` can be broader paraphrases, but keep them retrieval-oriented rather than full-sentence prose.
- Downweight legislative boilerplate.
"""


def _fallback_search_phrases(text: str) -> list[str]:
    normalized = re.sub(r"[^a-zA-Z0-9\\s]", " ", text.lower())
    tokens = [token for token in normalized.split() if len(token) > 4]
    counts = Counter(tokens)
    common = [word for word, _ in counts.most_common(10)]
    phrases = [" ".join(common[idx : idx + 3]).strip() for idx in range(0, min(len(common), 8), 2)]
    return [phrase for phrase in phrases if phrase]


def _fallback_profile(bill_text: str) -> UploadedBillProfile:
    lines = [line.strip() for line in bill_text.splitlines() if line.strip()]
    title = lines[0][:140] if lines else "Uploaded bill"
    summary_text = " ".join(lines[:20])[:1200]
    description = summary_text[:240]
    return UploadedBillProfile(
        title=title,
        description=description,
        summary=summary_text,
        policy_domain=[],
        policy_intent=summary_text[:300],
        legal_mechanisms=[],
        affected_entities=[],
        enforcement_mechanisms=[],
        fiscal_elements=[],
        bill_type_hints=[],
        jurisdiction_hints=[],
        search_phrases=_fallback_search_phrases(summary_text),
    )


class BillProfileExtractor:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = CodexClient()

    def extract(self, bill_text: str) -> UploadedBillProfile:
        trimmed_bill_text = bill_text[: self.settings.max_bill_chars_for_llm]
        user_prompt = (
            "Profile this uploaded bill for high-recall similarity search.\n\n"
            "Return only the JSON object.\n\n"
            f"Bill text:\n{trimmed_bill_text}"
        )
        try:
            payload = self.client.chat_json(system_prompt=PROFILE_SYSTEM_PROMPT, user_prompt=user_prompt)
            return UploadedBillProfile.model_validate(payload)
        except Exception:
            return _fallback_profile(trimmed_bill_text)
