import json
import re
from typing import Any, Dict, Optional

def load_file(file_path: str, is_json: bool = False) -> Any:
    with open(file_path, "r", encoding="utf-8") as f:
        if is_json:
            return json.load(f)
        else:
            return f.read()

def load_prompt_template(file_path: str, template_args: Optional[Dict[str, Any]] = None) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    if template_args:
        pattern = re.compile(r"(?<!\{)\{([A-Za-z_][A-Za-z0-9_]*)\}(?!\})")

        def replacer(match: re.Match) -> str:
            key = match.group(1)
            if key in template_args:
                value = template_args[key]
                return "" if value is None else str(value)
            return match.group(0)

        return pattern.sub(replacer, template)
    
    return template