from __future__ import annotations

import math
import re
from functools import lru_cache

import numpy as np
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer

from step1.config import get_settings
from step1.models import CandidateBill, UploadedBillProfile


GENERIC_CONCEPT_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "following",
    "from",
    "if",
    "include",
    "including",
    "in",
    "into",
    "is",
    "it",
    "its",
    "not",
    "of",
    "on",
    "or",
    "solely",
    "that",
    "the",
    "their",
    "these",
    "this",
    "to",
    "under",
    "was",
    "were",
    "with",
    "within",
}


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_overlap_text(text: str) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    return _normalize_whitespace(text.lower())


def _concept_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalize_overlap_text(text))
    return {
        token
        for token in tokens
        if (len(token) >= 3 or token in {"dds", "wic"}) and token not in GENERIC_CONCEPT_STOPWORDS
    }


def _query_terms(profile: UploadedBillProfile) -> set[str]:
    parts = [
        profile.title,
        profile.description,
        profile.policy_intent,
        *profile.search_phrases,
        *profile.policy_domain,
        *profile.legal_mechanisms,
        *profile.affected_entities,
        *profile.enforcement_mechanisms,
    ]
    terms: set[str] = set()
    for part in parts:
        terms.update(_concept_tokens(part))
    return terms


def _candidate_terms(candidate: CandidateBill) -> set[str]:
    parts = [
        candidate.title,
        " ".join(candidate.subjects),
        candidate.latest_action_description,
        candidate.excerpt,
    ]
    terms: set[str] = set()
    for part in parts:
        terms.update(_concept_tokens(part))
    return terms


def _broad_bill_penalty(profile: UploadedBillProfile, candidate: CandidateBill) -> float:
    candidate_title = (candidate.title or "").lower()
    profile_text = " ".join([profile.title, *profile.bill_type_hints, *profile.search_phrases]).lower()
    if any(term in profile_text for term in ("budget act", "budget", "trailer", "appropriation", "omnibus")):
        return 0.0
    if any(term in candidate_title for term in ("budget act", "trailer bill", "trailer", "omnibus")):
        return 0.08
    return 0.0


def _best_excerpt(raw_text: str, search_terms: list[str], char_limit: int) -> str:
    clean_text = _normalize_whitespace(raw_text)
    if not clean_text:
        return ""
    lowered = clean_text.lower()
    for term in search_terms:
        normalized = _normalize_whitespace(term).lower()
        if len(normalized) < 5:
            continue
        idx = lowered.find(normalized[:80])
        if idx >= 0:
            start = max(0, idx - char_limit // 4)
            end = min(len(clean_text), start + char_limit)
            return clean_text[start:end]
    return clean_text[:char_limit]


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model, device=settings.embedding_device)


class SemanticRanker:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _query_text(self, profile: UploadedBillProfile) -> str:
        parts = [
            profile.title,
            profile.description,
            profile.summary,
            profile.policy_intent,
            " ".join(profile.policy_domain),
            " ".join(profile.legal_mechanisms),
            " ".join(profile.affected_entities),
            " ".join(profile.enforcement_mechanisms),
            " ".join(profile.search_phrases),
        ]
        return "\n".join(part for part in parts if part).strip()

    def rerank(self, profile: UploadedBillProfile, candidates: list[CandidateBill]) -> list[CandidateBill]:
        if not candidates:
            return []

        model = _load_model()
        search_terms = [profile.title, *profile.search_phrases, *profile.legal_mechanisms, *profile.policy_domain]
        query_text = self._query_text(profile)
        query_terms = _query_terms(profile)
        candidate_docs: list[str] = []

        for candidate in candidates:
            candidate.excerpt = _best_excerpt(candidate.raw_text, search_terms, self.settings.excerpt_char_limit)
            doc = "\n".join(
                part
                for part in [
                    candidate.title,
                    " ".join(candidate.subjects),
                    candidate.latest_action_description,
                    candidate.excerpt,
                ]
                if part
            )
            candidate_docs.append(doc)

        embeddings = model.encode(
            [query_text, *candidate_docs],
            batch_size=self.settings.embedding_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_embedding = embeddings[0]
        candidate_embeddings = embeddings[1:]

        for idx, candidate in enumerate(candidates):
            semantic = float(np.dot(query_embedding, candidate_embeddings[idx]))
            title_similarity = fuzz.token_set_ratio(profile.title, candidate.title) / 100.0 if profile.title else 0.0
            candidate_terms = _candidate_terms(candidate)
            concept_overlap = 0.0
            if query_terms and candidate_terms:
                concept_overlap = len(query_terms & candidate_terms) / max(1, min(len(query_terms), 18))

            jurisdiction_boost = 0.0
            if candidate.state_code and candidate.state_code in {hint.lower() for hint in profile.jurisdiction_hints}:
                jurisdiction_boost = 0.05

            broad_penalty = _broad_bill_penalty(profile, candidate)

            candidate.semantic_score = max(
                0.0,
                min(
                    1.0,
                    semantic * 0.65
                    + title_similarity * 0.15
                    + concept_overlap * 0.10
                    + min(1.0, candidate.lexical_score / 6.0) * 0.10
                    + jurisdiction_boost,
                ),
            )
            if broad_penalty:
                candidate.semantic_score = max(0.0, candidate.semantic_score - broad_penalty)

        return sorted(candidates, key=lambda item: item.semantic_score, reverse=True)
