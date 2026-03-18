from __future__ import annotations

from pathlib import Path


PROMPT_ROOT = Path(__file__).resolve().parents[3] / "data" / "prompts"


def load_prompt(name: str) -> str:
    path = PROMPT_ROOT / name
    return path.read_text(encoding="utf-8").strip()
