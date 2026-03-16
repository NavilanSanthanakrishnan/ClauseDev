from __future__ import annotations

import math
import re
from collections import Counter, OrderedDict
from functools import lru_cache

import numpy as np
from sentence_transformers import SentenceTransformer

from step4.config import get_settings
from step4.models import LegalCandidate, UploadedBillProfile
from step4.services.database import Database
from step4.services.legal_index import alias_forms, normalize_citation


GENERIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "may",
    "must",
    "no",
    "not",
    "of",
    "on",
    "or",
    "shall",
    "that",
    "the",
    "this",
    "to",
    "under",
    "with",
}

CALIFORNIA_CODE_NAMES = {
    "labor code": "LAB",
    "welfare and institutions code": "WIC",
    "government code": "GOV",
    "health and safety code": "HSC",
    "penal code": "PEN",
}


def _normalize_text(text: str) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text or "")
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_tsquery(text: str) -> str:
    text = _normalize_text(text)
    text = re.sub(r"[^A-Za-z0-9\s\-./§]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _important_tokens(text: str) -> list[str]:
    normalized = _normalize_text(text).lower()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [token for token in tokens if len(token) >= 3 and token not in GENERIC_STOPWORDS]


def _query_terms(profile: UploadedBillProfile) -> set[str]:
    parts = [
        profile.title,
        profile.summary,
        *profile.policy_domains,
        *profile.affected_entities,
        *profile.required_actions,
        *profile.prohibited_actions,
        *profile.permissions_created,
        *profile.enforcement_mechanisms,
        *profile.named_agencies,
        *profile.conflict_search_phrases,
    ]
    terms: set[str] = set()
    for part in parts:
        terms.update(_important_tokens(part))
    return terms


def _candidate_terms(candidate: LegalCandidate) -> set[str]:
    parts = [candidate.citation, candidate.heading, candidate.hierarchy_path, candidate.excerpt]
    terms: set[str] = set()
    for part in parts:
        terms.update(_important_tokens(part))
    return terms


def _best_excerpt(raw_text: str, search_terms: list[str], char_limit: int) -> str:
    clean_text = _normalize_text(raw_text)
    if not clean_text:
        return ""
    lowered = clean_text.lower()
    for term in search_terms:
        normalized = _normalize_text(term).lower()
        if len(normalized) < 5:
            continue
        idx = lowered.find(normalized[:80])
        if idx >= 0:
            start = max(0, idx - char_limit // 3)
            end = min(len(clean_text), start + char_limit)
            return clean_text[start:end]
    return clean_text[:char_limit]


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    settings = get_settings()
    return SentenceTransformer(
        settings.embedding_model,
        device=settings.embedding_device,
        local_files_only=True,
    )


class LegalRetriever:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.settings = get_settings()

    def retrieve(self, profile: UploadedBillProfile) -> dict[str, list[LegalCandidate]]:
        california = self._retrieve_california(profile)
        federal = self._retrieve_uscode(profile)
        california = self._semantic_rerank(profile, california)
        federal = self._semantic_rerank(profile, federal)
        return {
            "california": california[: self.settings.llm_input_limit],
            "federal": federal[: self.settings.llm_input_limit],
        }

    def _query_phrases(self, profile: UploadedBillProfile) -> list[str]:
        raw_sources = [
            profile.title,
            profile.summary,
            *profile.required_actions,
            *profile.prohibited_actions,
            *profile.permissions_created,
            *profile.enforcement_mechanisms,
            *profile.named_agencies,
            *profile.explicit_citations,
            *profile.conflict_search_phrases,
            *(clause.text for clause in profile.key_clauses),
        ]
        weighted_queries: dict[str, float] = {}

        def add_query(text: str, weight: float) -> None:
            normalized = _sanitize_tsquery(text)
            if len(normalized) < 4:
                return
            key = normalized.lower()
            if key not in weighted_queries or weighted_queries[key] < weight:
                weighted_queries[key] = weight

        token_counts: Counter[str] = Counter()
        for source in raw_sources:
            token_counts.update(set(_important_tokens(source)))

        for source in raw_sources:
            normalized = _sanitize_tsquery(source)
            tokens = _important_tokens(normalized)
            if 2 <= len(tokens) <= 7:
                add_query(" ".join(tokens), len(tokens) + sum(token_counts[token] for token in set(tokens)))
            for size in (2, 3, 4):
                if len(tokens) < size:
                    continue
                for idx in range(0, len(tokens) - size + 1):
                    window = tokens[idx : idx + size]
                    weight = size * 2 + sum(token_counts[token] for token in set(window))
                    add_query(" ".join(window), weight)

        for citation in self._citation_sources(profile):
            add_query(citation, 20.0)

        combined_source_text = " | ".join(raw_sources).lower()
        if "minimum wage" in combined_source_text:
            add_query("29 U.S.C. 206 minimum wage", 24.0)
            add_query("29 U.S.C. 218 minimum wage higher state local ordinance", 25.0)
            add_query("municipal ordinance minimum wage higher", 24.0)
        if "overtime" in combined_source_text or "40 hours" in combined_source_text or "workweek" in combined_source_text:
            add_query("29 U.S.C. 207 overtime 40 hours workweek", 25.0)
            add_query("29 U.S.C. 218 maximum workweek lower", 24.0)
        if "state local minimum wage" in combined_source_text or "higher hourly minimum wage" in combined_source_text:
            add_query("higher state local minimum wage preserved", 24.0)
            add_query("state law municipal ordinance higher minimum wage", 24.0)

        ranked = [
            query
            for query, _ in sorted(weighted_queries.items(), key=lambda item: (-item[1], len(item[0]), item[0]))
        ]
        return list(OrderedDict.fromkeys(ranked))[:14]

    def _citation_sources(self, profile: UploadedBillProfile) -> list[str]:
        return list(
            OrderedDict.fromkeys(
                [
                    *profile.explicit_citations,
                    *profile.amended_citations,
                    *profile.repealed_citations,
                    *profile.conflict_search_phrases,
                ]
            )
        )

    def _normalized_california_citations(self, profile: UploadedBillProfile) -> list[str]:
        matches: list[str] = []
        for citation in self._citation_sources(profile):
            raw = citation.strip()
            if not raw:
                continue
            upper = raw.upper().replace("SECTION", "").replace("§", " ").strip()
            upper = re.sub(r"\s+", " ", upper)
            if re.match(r"^[A-Z]{2,5}\s+\d", upper):
                matches.append(upper.rstrip("."))
                continue
            lowered = raw.lower()
            for code_name, code_abbrev in CALIFORNIA_CODE_NAMES.items():
                if code_name in lowered:
                    number_match = re.search(r"(\d+(?:\.\d+)*)", raw)
                    if number_match:
                        matches.append(f"{code_abbrev} {number_match.group(1)}")
        return list(OrderedDict.fromkeys(matches))

    def _normalized_uscode_citations(self, profile: UploadedBillProfile) -> list[str]:
        matches: list[str] = []
        for citation in self._citation_sources(profile):
            match = re.search(r"(\d+)\s*U\.?S\.?C\.?\s*(?:§+)?\s*([0-9A-Za-z.\-()]+)", citation, re.IGNORECASE)
            if match:
                matches.append(f"{match.group(1)} U.S.C. § {match.group(2)}")
        return list(OrderedDict.fromkeys(matches))

    def _retrieve_california(self, profile: UploadedBillProfile) -> list[LegalCandidate]:
        prioritized_citations = list(
            OrderedDict.fromkeys(
                [
                    *self._normalized_california_citations(
                        profile.model_copy(update={"explicit_citations": profile.amended_citations})
                    ),
                    *self._normalized_california_citations(profile),
                ]
            )
        )
        return self._retrieve_from_legal_index(
            profile,
            source_system="california",
            jurisdiction="CA",
            lexical_limit=self.settings.california_lexical_limit,
            prioritized_citations=prioritized_citations,
        )

    def _retrieve_uscode(self, profile: UploadedBillProfile) -> list[LegalCandidate]:
        return self._retrieve_from_legal_index(
            profile,
            source_system="federal",
            jurisdiction="US",
            lexical_limit=self.settings.uscode_lexical_limit,
            prioritized_citations=self._normalized_uscode_citations(profile),
        )

    def _retrieve_from_legal_index(
        self,
        profile: UploadedBillProfile,
        *,
        source_system: str,
        jurisdiction: str,
        lexical_limit: int,
        prioritized_citations: list[str],
    ) -> list[LegalCandidate]:
        candidates: dict[tuple[str, str], LegalCandidate] = {}
        queries = self._query_phrases(profile)
        for query in queries:
            sanitized = _sanitize_tsquery(query)
            if not sanitized:
                continue
            rows = self.db.legal_index.fetch_all(
                """
                SELECT
                    document_id,
                    source_kind,
                    citation,
                    COALESCE(heading, citation) AS heading,
                    COALESCE(hierarchy_path, '') AS hierarchy_path,
                    source_url,
                    body_text,
                    ts_rank_cd(search_text, websearch_to_tsquery('english', %(query)s)) AS rank
                FROM legal_document_search
                WHERE source_system = %(source_system)s
                  AND jurisdiction = %(jurisdiction)s
                  AND search_text @@ websearch_to_tsquery('english', %(query)s)
                ORDER BY rank DESC
                LIMIT %(limit)s
                """,
                {
                    "query": sanitized,
                    "source_system": source_system,
                    "jurisdiction": jurisdiction,
                    "limit": lexical_limit,
                },
            )
            self._merge_candidates(candidates, rows, query, source_system, None)

        for idx, citation in enumerate(prioritized_citations):
            exact_rows = self.db.legal_index.fetch_all(
                """
                SELECT
                    d.document_id,
                    d.source_kind,
                    d.citation,
                    COALESCE(d.heading, d.citation) AS heading,
                    COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                    d.source_url,
                    d.body_text,
                    1.0 AS rank
                FROM legal_documents d
                WHERE d.source_system = %(source_system)s
                  AND d.jurisdiction = %(jurisdiction)s
                  AND d.normalized_citation = %(normalized_citation)s
                LIMIT 20
                """,
                {
                    "source_system": source_system,
                    "jurisdiction": jurisdiction,
                    "normalized_citation": normalize_citation(citation),
                },
            )
            self._merge_candidates(candidates, exact_rows, citation, source_system, None, exact_boost=2.4 if idx == 0 else 1.8)

            alias_seen = set()
            for alias in alias_forms(citation):
                alias_rows = self.db.legal_index.fetch_all(
                    """
                    SELECT
                        d.document_id,
                        d.source_kind,
                        d.citation,
                        COALESCE(d.heading, d.citation) AS heading,
                        COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                        d.source_url,
                        d.body_text,
                        0.9 AS rank
                    FROM legal_aliases a
                    JOIN legal_documents d
                      ON d.document_id = a.document_id
                    WHERE d.source_system = %(source_system)s
                      AND d.jurisdiction = %(jurisdiction)s
                      AND a.normalized_alias = %(normalized_alias)s
                    LIMIT 20
                    """,
                    {
                        "source_system": source_system,
                        "jurisdiction": jurisdiction,
                        "normalized_alias": normalize_citation(alias),
                    },
                )
                for row in alias_rows:
                    alias_seen.add(row["citation"])
                self._merge_candidates(candidates, alias_rows, alias, source_system, None, exact_boost=1.6)

                reference_rows = self.db.legal_index.fetch_all(
                    """
                    SELECT
                        d.document_id,
                        d.source_kind,
                        d.citation,
                        COALESCE(d.heading, d.citation) AS heading,
                        COALESCE(d.hierarchy_path, '') AS hierarchy_path,
                        d.source_url,
                        d.body_text,
                        0.7 AS rank
                    FROM legal_references r
                    JOIN legal_documents d
                      ON d.document_id = r.document_id
                    WHERE d.source_system = %(source_system)s
                      AND d.jurisdiction = %(jurisdiction)s
                      AND r.normalized_referenced_citation = %(normalized_alias)s
                    LIMIT 20
                    """,
                    {
                        "source_system": source_system,
                        "jurisdiction": jurisdiction,
                        "normalized_alias": normalize_citation(alias),
                    },
                )
                self._merge_candidates(candidates, reference_rows, alias, source_system, None, exact_boost=1.25)

        return self._finalize_candidates(profile, list(candidates.values()))

    def _merge_candidates(
        self,
        existing: dict[tuple[str, str], LegalCandidate],
        rows: list[dict],
        query: str,
        source_system: str,
        source_kind: str | None,
        exact_boost: float = 1.0,
    ) -> None:
        for row in rows:
            key = (source_system, row["citation"])
            if key not in existing:
                existing[key] = LegalCandidate(
                    document_id=row["document_id"],
                    source_system=source_system,
                    source_kind=(row.get("source_kind") or source_kind or "section"),
                    citation=row["citation"],
                    heading=row.get("heading") or "",
                    hierarchy_path=row.get("hierarchy_path") or "",
                    source_url=row.get("source_url"),
                    body_text=row.get("body_text") or "",
                )
            candidate = existing[key]
            candidate.lexical_score += float(row.get("rank") or 0.0) * exact_boost
            if query not in candidate.matched_queries:
                candidate.matched_queries.append(query)
            if (row.get("source_kind") or source_kind) == "provision" and candidate.source_kind != "provision":
                candidate.source_kind = "provision"

    def _finalize_candidates(self, profile: UploadedBillProfile, candidates: list[LegalCandidate]) -> list[LegalCandidate]:
        if not candidates:
            return []
        search_terms = [
            profile.title,
            *profile.conflict_search_phrases,
            *profile.explicit_citations,
            *(clause.text for clause in profile.key_clauses),
        ]
        for candidate in candidates:
            candidate.excerpt = _best_excerpt(candidate.body_text, search_terms, self.settings.excerpt_char_limit)
        return sorted(candidates, key=lambda item: item.lexical_score, reverse=True)[: self.settings.semantic_input_limit]

    def _semantic_rerank(self, profile: UploadedBillProfile, candidates: list[LegalCandidate]) -> list[LegalCandidate]:
        if not candidates:
            return []

        model = _load_model()
        query_text = "\n".join(
            part
            for part in [
                profile.title,
                profile.summary,
                " ".join(profile.policy_domains),
                " ".join(profile.required_actions),
                " ".join(profile.prohibited_actions),
                " ".join(profile.permissions_created),
                " ".join(profile.named_agencies),
                " ".join(profile.conflict_search_phrases),
                " ".join(clause.text for clause in profile.key_clauses),
            ]
            if part
        )
        docs = [
            "\n".join(part for part in [candidate.citation, candidate.heading, candidate.hierarchy_path, candidate.excerpt] if part)
            for candidate in candidates
        ]
        embeddings = model.encode(
            [query_text, *docs],
            batch_size=self.settings.embedding_batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        query_embedding = embeddings[0]
        query_terms = _query_terms(profile)
        candidate_embeddings = embeddings[1:]

        for idx, candidate in enumerate(candidates):
            semantic = float(np.dot(query_embedding, candidate_embeddings[idx]))
            candidate_terms = _candidate_terms(candidate)
            overlap = 0.0
            if query_terms and candidate_terms:
                overlap = len(query_terms & candidate_terms) / max(1, math.sqrt(len(query_terms) * len(candidate_terms)))
            candidate.semantic_score = max(
                0.0,
                min(1.0, semantic * 0.72 + min(1.0, overlap) * 0.18 + min(1.0, candidate.lexical_score / 12.0) * 0.10),
            )
            candidate.final_score = candidate.semantic_score * 0.7 + min(1.0, candidate.lexical_score / 12.0) * 0.3

        return sorted(candidates, key=lambda item: item.final_score, reverse=True)
