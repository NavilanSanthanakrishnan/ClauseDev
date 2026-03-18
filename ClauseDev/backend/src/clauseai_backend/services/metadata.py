import re
from collections import Counter


STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "with",
    "shall",
    "this",
    "from",
    "into",
    "such",
    "under",
    "bill",
    "section",
    "state",
    "act",
    "law",
}


def generate_metadata_from_text(text: str, fallback_title: str) -> dict[str, object]:
    normalized = " ".join(text.split())
    title = _extract_title(text) or fallback_title
    description = normalized[:280].strip()
    summary = normalized[:700].strip()
    keywords = _extract_keywords(normalized)
    return {
      "title": title,
      "description": description,
      "summary": summary,
      "keywords": keywords,
    }


def _extract_title(text: str) -> str | None:
    for line in text.splitlines():
        candidate = line.strip()
        if len(candidate) > 10 and len(candidate) < 160:
            return candidate
    return None


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z-]{3,}", text.lower())
    counts = Counter(word for word in words if word not in STOPWORDS)
    return [word for word, _ in counts.most_common(8)]
