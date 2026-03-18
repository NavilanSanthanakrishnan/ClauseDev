from __future__ import annotations

from collections import defaultdict
from typing import Any

from clause_backend.repositories import laws
from clause_backend.schemas import LawDetail, LawFilterOptions, LawListItem, LawSearchFilters, LawSearchResponse, LawStatsResponse
from clause_backend.services.standard_search import normalize_tokens


LAW_JURISDICTION_HINTS = {
    "california": "California",
    "ca ": "California",
    "cal.": "California",
    "federal": "United States",
    "united states": "United States",
    "u.s.": "United States",
    "usc": "United States",
}


LAW_CONCEPT_EXPANSIONS = {
    "conflict": ["contradict", "preempt", "inconsistent", "notwithstanding", "prohibit"],
    "contradict": ["conflict", "preempt", "inconsistent", "opposite"],
    "wildfire": ["fire", "burn", "forest", "hazard", "risk"],
    "privacy": ["consumer", "data", "broker", "deletion", "surveillance"],
    "employment": ["worker", "employee", "wage", "labor", "retaliation"],
}


def normalize_citation_text(text: str) -> str:
    return "".join(character for character in text.upper() if character.isalnum())


def law_stats() -> LawStatsResponse:
    return LawStatsResponse(**laws.law_stats())


def law_filter_options() -> LawFilterOptions:
    return LawFilterOptions(**laws.law_filter_options())


def infer_law_filters(query: str, filters: LawSearchFilters) -> LawSearchFilters:
    lowered = query.lower()
    if filters.jurisdiction:
        return filters
    for token, jurisdiction in LAW_JURISDICTION_HINTS.items():
        if token in lowered:
            return filters.model_copy(update={"jurisdiction": jurisdiction})
    return filters


def expand_law_terms(query: str) -> list[str]:
    tokens = normalize_tokens(query)
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(LAW_CONCEPT_EXPANSIONS.get(token, []))
    return list(dict.fromkeys(expanded))


def _text_blob(item: dict[str, Any]) -> str:
    return " ".join(
        [
            item.get("citation", ""),
            item.get("heading") or "",
            item.get("hierarchy_path") or "",
            item.get("body_excerpt") or "",
        ]
    ).lower()


def _match_coverage(item: dict[str, Any], terms: list[str]) -> tuple[int, int]:
    if not terms:
        return 0, 0
    blob = _text_blob(item)
    matched = sum(1 for term in terms if term.lower() in blob)
    return matched, len(terms)


def _phrase_score(item: dict[str, Any], query: str) -> float:
    lowered_query = query.lower().strip()
    if not lowered_query:
        return 0.0
    citation = item.get("citation", "").lower()
    heading = (item.get("heading") or "").lower()
    excerpt = (item.get("body_excerpt") or "").lower()
    if lowered_query == citation:
        return 90.0
    if lowered_query in citation:
        return 40.0
    if lowered_query in heading:
        return 12.0
    if lowered_query in excerpt:
        return 8.0
    return 0.0


def _citation_score(item: dict[str, Any], query: str) -> float:
    normalized_query = normalize_citation_text(query)
    normalized_citation = normalize_citation_text(item.get("citation", ""))
    if not normalized_query or not normalized_citation:
        return 0.0
    if normalized_query == normalized_citation:
        return 140.0
    if normalized_citation.startswith(normalized_query):
        return 60.0
    if normalized_query in normalized_citation:
        return 35.0
    return 0.0


def _source_allowed(item: dict[str, Any], filters: LawSearchFilters) -> bool:
    if filters.jurisdiction and item.get("jurisdiction") != filters.jurisdiction:
        return False
    if filters.source and item.get("source") != filters.source:
        return False
    return True


def _collect_candidates(query: str, filters: LawSearchFilters) -> list[dict[str, Any]]:
    pool_limit = max(filters.limit * 3, 24)
    results: list[dict[str, Any]] = []
    if not filters.source or filters.source == "California Code":
        results.extend(laws.search_california_laws(query, pool_limit))
    if not filters.source or filters.source == "United States Code":
        results.extend(laws.search_uscode_laws(query, pool_limit))
    return [item for item in results if _source_allowed(item, filters)]


def search_laws(query: str, filters: LawSearchFilters) -> LawSearchResponse:
    effective_filters = infer_law_filters(query, filters)
    terms = expand_law_terms(query)
    candidates = _collect_candidates(query, effective_filters)

    candidate_scores: dict[str, float] = defaultdict(float)
    candidate_payloads: dict[str, dict[str, Any]] = {}
    candidate_reasons: dict[str, list[str]] = defaultdict(list)

    for item in candidates:
        document_id = str(item["document_id"])
        candidate_payloads[document_id] = item
        lexical_rank = float(item.get("lexical_rank") or 0.0)
        candidate_scores[document_id] += lexical_rank * 30.0
        matched_terms, total_terms = _match_coverage(item, terms)
        if matched_terms:
            candidate_scores[document_id] += (matched_terms / total_terms) * 24.0
            candidate_reasons[document_id].append(f"Matched {matched_terms} of {total_terms} legal search terms")
        phrase_score = _phrase_score(item, query)
        if phrase_score:
            candidate_scores[document_id] += phrase_score
            candidate_reasons[document_id].append("Direct citation or phrase alignment")
        citation_score = _citation_score(item, query)
        if citation_score:
            candidate_scores[document_id] += citation_score
            candidate_reasons[document_id].append("Citation normalized exactly")
        if effective_filters.jurisdiction and item["jurisdiction"] == effective_filters.jurisdiction:
            candidate_scores[document_id] += 8.0
            candidate_reasons[document_id].append(f"Jurisdiction matched {effective_filters.jurisdiction}")
        candidate_reasons[document_id].append(f"Retrieved from {item['source']}")

    ranked_items = sorted(
        candidate_payloads.values(),
        key=lambda item: (
            candidate_scores[item["document_id"]],
            item.get("citation", ""),
        ),
        reverse=True,
    )[: filters.limit]

    return LawSearchResponse(
        mode="standard",
        query=query,
        explanation="Standard law search combines jurisdiction inference, PostgreSQL full-text retrieval, citation matching, and deterministic reranking.",
        plan={
            "effective_filters": effective_filters.model_dump(),
            "expanded_terms": terms[:12],
            "candidate_count": len(candidate_payloads),
        },
        items=[
            LawListItem(
                document_id=item["document_id"],
                citation=item["citation"],
                jurisdiction=item["jurisdiction"],
                source=item["source"],
                heading=item.get("heading"),
                hierarchy_path=item.get("hierarchy_path"),
                body_excerpt=item.get("body_excerpt"),
                source_url=item.get("source_url"),
                matched_reasons=list(dict.fromkeys(candidate_reasons[item["document_id"]]))[:4],
                relevance_score=round(candidate_scores[item["document_id"]], 2),
            )
            for item in ranked_items
        ],
    )


def get_law_detail(document_id: str) -> LawDetail | None:
    payload: dict[str, Any] | None = None
    if document_id.startswith("ca_code:"):
        payload = laws.get_california_law(document_id.split(":", 1)[1])
    elif document_id.startswith("uscode:"):
        payload = laws.get_uscode_law(document_id.split(":", 1)[1])

    if not payload:
        return None

    return LawDetail(
        document_id=payload["document_id"],
        citation=payload["citation"],
        jurisdiction=payload["jurisdiction"],
        source=payload["source"],
        heading=payload.get("heading"),
        hierarchy_path=payload.get("hierarchy_path"),
        body_excerpt=(payload.get("body_text") or "")[:1200],
        source_url=payload.get("source_url"),
        matched_reasons=[],
        relevance_score=0.0,
        body_text=payload.get("body_text") or "",
    )
