import asyncio
import json
import re
import logging
from typing import Any, Callable, Dict, List

from app.core.config import DEFAULT_MODEL
from app.services.llm_client import LLMClient
from app.utils import extract_json_from_text

logger = logging.getLogger(__name__)

TOOL_ARTIFACT_PATTERN = re.compile(
    r"<tool_call>|<function=|<parameter=", re.IGNORECASE
)
HUNK_HEADER_PATTERN = re.compile(
    r"^@@\s-\d+(?:,\d+)?\s\+\d+(?:,\d+)?\s@@", re.MULTILINE
)
PATCH_LINE_PATTERN = re.compile(r"^(?:\+|-)", re.MULTILINE)

def is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())

def normalize_phase(phase: str | None) -> str:
    return (phase or "report").strip().lower()

def iter_json_dict_candidates(text: str) -> list[Dict[str, Any]]:
    if not text or not isinstance(text, str):
        return []

    decoder = json.JSONDecoder()
    candidates: list[Dict[str, Any]] = []
    seen: set[str] = set()

    def _append_candidate(value: Any) -> None:
        if isinstance(value, dict):
            try:
                key = json.dumps(value, sort_keys=True, ensure_ascii=False)
            except Exception:
                key = repr(value)
            if key not in seen:
                seen.add(key)
                candidates.append(value)
            return
        if isinstance(value, list):
            for item in value:
                _append_candidate(item)

    _append_candidate(extract_json_from_text(text))

    for match in re.finditer(r"[{[]", text):
        start = match.start()
        snippet = text[start:]
        try:
            parsed, _ = decoder.raw_decode(snippet)
        except json.JSONDecodeError:
            continue
        _append_candidate(parsed)

    return candidates

def sanitize_analysis_text(raw_text: str, structured_data: Dict[str, Any] | None) -> str:
    if not isinstance(raw_text, str):
        return json.dumps(structured_data or {}, indent=2)
    if TOOL_ARTIFACT_PATTERN.search(raw_text):
        return json.dumps(structured_data or {}, indent=2)
    return raw_text

def normalize_change_structure(item: Dict[str, Any]) -> Dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    if all(key in item for key in ("operation", "target", "content")):
        return item

    nested_change = item.get("change")
    if isinstance(nested_change, dict) and all(
        key in nested_change for key in ("operation", "target", "content")
    ):
        return {**item, **nested_change}
    return None

def validate_report_context_for_fixes(report_context: Any) -> str | None:
    if not isinstance(report_context, dict):
        return "Missing report_context for fixes phase"
    if not is_non_empty_string(report_context.get("analysis")) or not isinstance(
        report_context.get("structured_data"), dict
    ):
        return "Missing report_context.analysis or report_context.structured_data for fixes phase"
    return None

def validate_hunk_change(change: Any) -> str | None:
    if not is_non_empty_string(change):
        return "change must be a non-empty string"

    patch_text = change.strip()
    if not HUNK_HEADER_PATTERN.search(patch_text):
        return "change must include at least one unified hunk header (@@ -old,+new @@)"
    if not PATCH_LINE_PATTERN.search(patch_text):
        return "change must include at least one patch line starting with '+' or '-'"
    return None

def build_fixes_classification_payload(
    improvements: list[Any],
    invalid_improvements: list[Dict[str, Any]],
) -> Dict[str, Any]:
    valid_improvement_indices: list[int] = []
    invalid_indices = {
        entry.get("index")
        for entry in invalid_improvements
        if isinstance(entry, dict) and isinstance(entry.get("index"), int)
    }

    for idx, _ in enumerate(improvements):
        if idx not in invalid_indices:
            valid_improvement_indices.append(idx)

    synthetic_invalid_count = sum(
        1
        for entry in invalid_improvements
        if not isinstance(entry, dict) or entry.get("index") is None
    )
    total_items = len(improvements) if improvements else synthetic_invalid_count

    payload: Dict[str, Any] = {
        "improvements": improvements,
        "valid_improvement_indices": valid_improvement_indices,
        "invalid_improvements": invalid_improvements,
        "validation_summary": {
            "total": total_items,
            "valid": len(valid_improvement_indices),
            "invalid": len(invalid_improvements),
        },
    }

    if invalid_improvements:
        payload["warning"] = "Some generated patches were invalid and cannot be applied."

    return payload

def classify_fixes_improvements_payload(raw_text: str) -> Dict[str, Any]:
    parsed = extract_json_from_text(raw_text)
    if not isinstance(parsed, dict):
        return build_fixes_classification_payload(
            improvements=[],
            invalid_improvements=[
                {
                    "index": None,
                    "reason": "Failed to parse fixes JSON from response",
                    "item": {"raw_response": raw_text},
                }
            ],
        )

    improvements = parsed.get("improvements")
    if not isinstance(improvements, list):
        return build_fixes_classification_payload(
            improvements=[],
            invalid_improvements=[
                {
                    "index": None,
                    "reason": "Fixes payload must include top-level 'improvements' array",
                    "item": {"improvements": improvements},
                }
            ],
        )

    invalid_improvements: list[Dict[str, Any]] = []
    for idx, improvement in enumerate(improvements):
        if not isinstance(improvement, dict):
            invalid_improvements.append(
                {
                    "index": idx,
                    "reason": "Improvement must be an object",
                    "item": improvement,
                }
            )
            continue

        change_error = validate_hunk_change(improvement.get("change"))
        if change_error:
            invalid_improvements.append(
                {
                    "index": idx,
                    "reason": change_error,
                    "item": improvement,
                }
            )

    return build_fixes_classification_payload(
        improvements=improvements,
        invalid_improvements=invalid_improvements,
    )

async def force_json_retry(
    messages: list,
    prompt: str,
    extractor: Callable[[str], Any],
    sanitizer: Callable[[str, Any], str] | None = None,
) -> tuple[Any, str]:
    client = LLMClient()
    forced_messages = list(messages) + [{"role": "user", "content": prompt}]
    response = await asyncio.to_thread(
        client.chat, messages=forced_messages, model=DEFAULT_MODEL
    )
    repaired_raw = response.get("content", "")
    parsed = extractor(repaired_raw)
    if parsed is not None and sanitizer is not None:
        return parsed, sanitizer(repaired_raw, parsed)
    return parsed, repaired_raw

def _find_patch_line(
    bill_text: str,
    needle: str,
    replacement: str,
) -> Dict[str, Any] | None:
    if not is_non_empty_string(bill_text):
        return None

    lines = str(bill_text).splitlines()
    pattern = re.compile(re.escape(needle), re.IGNORECASE)

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if not pattern.search(line):
            continue
        new_line = pattern.sub(replacement, line, count=1)
        if new_line == line:
            continue
        return {"line_no": index, "old_line": line, "new_line": new_line}

    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        return {
            "line_no": index,
            "old_line": line,
            "new_line": f"{line} (clarified).",
        }
    return None

def _to_unified_patch(line_no: int, old_line: str, new_line: str) -> str:
    return "\n".join(
        [
            f"@@ -{line_no},1 +{line_no},1 @@",
            f"-{old_line}",
            f"+{new_line}",
        ]
    )

def build_fallback_improvements(
    bill_text: str,
    domain: str = "bill",
) -> List[Dict[str, Any]]:
    candidates_by_domain = {
        "bill": [
            {
                "needle": "shall",
                "replacement": "must",
                "title": "Use mandatory language",
                "explanation": "Replaces permissive drafting tone with mandatory language for clearer enforcement.",
                "section": "Requirements",
            },
            {
                "needle": "take effect immediately",
                "replacement": "take effect on January 1, 2027",
                "title": "Set implementation date",
                "explanation": "Adds a concrete implementation date to reduce transition ambiguity.",
                "section": "Implementation",
            },
        ],
        "legal": [
            {
                "needle": "shall enforce",
                "replacement": "shall enforce and issue implementing guidance",
                "title": "Clarify enforcement authority",
                "explanation": "Clarifies agency enforcement authority to reduce legal ambiguity.",
                "section": "Enforcement",
            },
            {
                "needle": "does not apply",
                "replacement": "does not apply only when documented by written findings",
                "title": "Narrow exemption scope",
                "explanation": "Narrows exemptions to reduce preemption and arbitrary enforcement risk.",
                "section": "Exemptions",
            },
        ],
        "stakeholder": [
            {
                "needle": "California Energy Commission",
                "replacement": "California Energy Commission, in consultation with local governments and small businesses,",
                "title": "Add stakeholder consultation",
                "explanation": "Adds consultation language to improve implementation feasibility for affected groups.",
                "section": "Stakeholder Engagement",
            },
            {
                "needle": "30-day correction period",
                "replacement": "60-day correction period with technical assistance",
                "title": "Phase in compliance support",
                "explanation": "Improves adoption by pairing penalties with a practical compliance window.",
                "section": "Implementation Support",
            },
        ],
    }

    candidates = candidates_by_domain.get(domain, candidates_by_domain["bill"])
    improvements: List[Dict[str, Any]] = []
    used_lines = set()

    for candidate in candidates:
        patch_line = _find_patch_line(
            bill_text,
            candidate["needle"],
            candidate["replacement"],
        )
        if not patch_line:
            continue
        if patch_line["line_no"] in used_lines:
            continue
        used_lines.add(patch_line["line_no"])

        patch = _to_unified_patch(
            patch_line["line_no"],
            patch_line["old_line"],
            patch_line["new_line"],
        )
        improvements.append(
            {
                "title": candidate["title"],
                "short_explanation": candidate["title"],
                "summary": candidate["title"],
                "explanation": candidate["explanation"],
                "improvement_type": candidate["section"],
                "optimization_strategy": candidate["section"],
                "metadata": {
                    "short_explanation": candidate["title"],
                    "explanation": candidate["explanation"],
                    "section": candidate["section"],
                },
                "change": patch,
            }
        )

    return improvements[:2]
