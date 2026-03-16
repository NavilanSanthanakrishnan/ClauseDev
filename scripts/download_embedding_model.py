#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from step1.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Downloading embedding model: {settings.embedding_model}")
    SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
    print("Embedding model ready.")


if __name__ == "__main__":
    main()
