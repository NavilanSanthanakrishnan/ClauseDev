import json
import re
from typing import Tuple, Any

def fix_incomplete_json(json_string: str) -> Tuple[Any, str]:
    if not json_string or not json_string.strip():
        return [], "[]"

    json_string = json_string.strip()

    json_string = re.sub(r'^```json\s*', '', json_string)
    json_string = re.sub(r'^```\s*', '', json_string)
    json_string = re.sub(r'\s*```$', '', json_string)

    try:
        result = json.loads(json_string)
        return result, json_string
    except json.JSONDecodeError:
        pass

    if not any(c in json_string for c in ['{', '[']):
        return [], "[]"

    last_complete_position = -1
    depth = 0
    in_string = False
    escape_next = False
    bracket_stack = []

    for i, char in enumerate(json_string):
        if escape_next:
            escape_next = False
            continue
        if char == '\\':
            escape_next = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char in '[{':
            bracket_stack.append(char)
            depth += 1
        elif char in ']}':
            if bracket_stack:
                bracket_stack.pop()
            depth -= 1
        elif char == ',' and depth == 1:
            last_complete_position = i

    if last_complete_position > 0:
        truncated = json_string[:last_complete_position]
        opened_brackets = 0
        opened_braces = 0
        in_string = False
        escape_next = False

        for char in truncated:
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '[':
                opened_brackets += 1
            elif char == ']':
                opened_brackets -= 1
            elif char == '{':
                opened_braces += 1
            elif char == '}':
                opened_braces -= 1

        closing = ']' * opened_brackets + '}' * opened_braces
        fixed = truncated + closing

        try:
            parsed = json.loads(fixed)
            return parsed, fixed
        except json.JSONDecodeError:
            pass

    for i in range(len(json_string) - 1, max(0, len(json_string) - 500), -1):
        test_str = json_string[:i]

        opened_brackets = 0
        opened_braces = 0
        in_string = False
        escape_next = False

        for char in test_str:
            if escape_next:
                escape_next = False
                continue
            if char == '\\':
                escape_next = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == '[':
                opened_brackets += 1
            elif char == ']':
                opened_brackets -= 1
            elif char == '{':
                opened_braces += 1
            elif char == '}':
                opened_braces -= 1

        if opened_brackets >= 0 and opened_braces >= 0:
            closing = ']' * opened_brackets + '}' * opened_braces
            fixed = test_str + closing

            try:
                parsed = json.loads(fixed)
                return parsed, fixed
            except json.JSONDecodeError:
                continue

    return [], "[]"