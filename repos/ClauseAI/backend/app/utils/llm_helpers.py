import json
import re
from typing import Dict, Any, List
from app.utils.data_handling import fix_incomplete_json

TOOL_TAG_PATTERN = re.compile(
    r"</?tool_call>|</?function(?:=[^>]*)?>|</?parameter(?:=[^>]*)?>",
    flags=re.IGNORECASE,
)
TRAILING_COMMA_PATTERN = re.compile(r",\s*([}\]])")
CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")

def _clean_json_like_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    cleaned = text.replace("\ufeff", "")
    cleaned = TOOL_TAG_PATTERN.sub("", cleaned)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    cleaned = TRAILING_COMMA_PATTERN.sub(r"\1", cleaned)
    cleaned = CONTROL_CHAR_PATTERN.sub("", cleaned)
    return cleaned.strip()

def _decode_from_any_start(candidate: str, decoder: json.JSONDecoder) -> Any:
    best_match = None
    best_score = (-1, -1)

    for match in re.finditer(r"[{\[]", candidate):
        start = match.start()
        snippet = candidate[start:]
        try:
            parsed, end = decoder.raw_decode(snippet)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, (dict, list)):
            continue
        # Ignore incidental empty arrays parsed from inside malformed objects.
        if isinstance(parsed, list) and parsed == [] and end <= 2:
            continue

        kind_score = 1 if isinstance(parsed, dict) else 0
        score = (kind_score, end)
        if score > best_score:
            best_match = parsed
            best_score = score

    return best_match

def _try_parse_candidate(candidate: str, decoder: json.JSONDecoder, depth: int = 0) -> Any:
    stripped = candidate.strip()
    if not stripped:
        return None

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, str) and depth < 2:
            nested = _try_parse_candidate(parsed, decoder, depth + 1)
            if nested is not None:
                return nested
        if isinstance(parsed, (dict, list)):
            return parsed
    except json.JSONDecodeError:
        pass

    cleaned = _clean_json_like_text(stripped)
    if cleaned and cleaned != stripped:
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, str) and depth < 2:
                nested = _try_parse_candidate(parsed, decoder, depth + 1)
                if nested is not None:
                    return nested
            if isinstance(parsed, (dict, list)):
                return parsed
        except json.JSONDecodeError:
            pass

        first_cleaned_json_start = None
        for i, char in enumerate(cleaned):
            if char in "{[":
                first_cleaned_json_start = i
                break
        if first_cleaned_json_start is not None and first_cleaned_json_start > 0:
            cleaned_fragment = cleaned[first_cleaned_json_start:].strip()
            try:
                parsed = json.loads(cleaned_fragment)
                if isinstance(parsed, str) and depth < 2:
                    nested = _try_parse_candidate(parsed, decoder, depth + 1)
                    if nested is not None:
                        return nested
                if isinstance(parsed, (dict, list)):
                    return parsed
            except json.JSONDecodeError:
                pass

    decoded = _decode_from_any_start(stripped, decoder)
    if decoded is not None:
        return decoded

    first_json_start = None
    for i, char in enumerate(stripped):
        if char in "{[":
            first_json_start = i
            break

    if first_json_start is not None:
        fragment = stripped[first_json_start:]
        fixed_data, _ = fix_incomplete_json(fragment)
        if isinstance(fixed_data, str) and depth < 2:
            nested = _try_parse_candidate(fixed_data, decoder, depth + 1)
            if nested is not None:
                return nested
        if isinstance(fixed_data, dict):
            return fixed_data
        if isinstance(fixed_data, list):
            # fix_incomplete_json returns [] when it cannot repair.
            # Only accept list output when the source fragment itself is an array.
            if fragment.lstrip().startswith("["):
                return fixed_data

    return None

def extract_json_from_text(text: str) -> Any:
    if not text:
        return None

    decoder = json.JSONDecoder()
    raw_text = str(text)

    candidates: List[str] = []
    fenced_matches = re.findall(r"```json\s*(.*?)\s*```", raw_text, flags=re.DOTALL | re.IGNORECASE)
    for block in fenced_matches:
        candidates.append(block)

    generic_fenced = re.findall(r"```\s*(.*?)\s*```", raw_text, flags=re.DOTALL)
    for block in generic_fenced:
        candidates.append(block)

    candidates.append(raw_text)
    cleaned_raw = _clean_json_like_text(raw_text)
    if cleaned_raw and cleaned_raw != raw_text:
        candidates.append(cleaned_raw)

    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        stripped = candidate.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)

        parsed = _try_parse_candidate(stripped, decoder)
        if parsed is not None:
            return parsed

        cleaned_candidate = _clean_json_like_text(stripped)
        if cleaned_candidate and cleaned_candidate != stripped:
            parsed = _try_parse_candidate(cleaned_candidate, decoder)
            if parsed is not None:
                return parsed

    return None

def _read_value(item: Any, key: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)

def build_tool_call_message(tool_calls: List[Any]) -> Dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": _read_value(tc, "id", ""),
                "type": "function",
                "function": {
                    "name": _read_value(_read_value(tc, "function", {}), "name", ""),
                    "arguments": _read_value(_read_value(tc, "function", {}), "arguments", "{}")
                }
            }
            for tc in tool_calls
        ]
    }

def build_tool_result_message(tool_call_id: str, content: str) -> Dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": content
    }
