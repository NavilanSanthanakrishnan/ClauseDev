from __future__ import annotations

from pathlib import Path


PROMPT_ROOTS = (
    Path(__file__).resolve().parents[3] / "data" / "prompts",
    Path(__file__).resolve().parents[4] / "prompts",
)


def load_prompt(name: str) -> str:
    for root in PROMPT_ROOTS:
        path = root / name
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(f"Prompt file {name} was not found in any configured prompt directory.")
