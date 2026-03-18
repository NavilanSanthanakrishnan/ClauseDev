from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any

from clause_backend.core.config import settings
from clause_backend.repositories import bills
from clause_backend.schemas import BillListItem, SearchFilters, SearchResponse
from clause_backend.services.gemini import embed_text

STATE_BY_NAME = {
    "alabama": "Alabama",
    "california": "California",
    "colorado": "Colorado",
    "georgia": "Georgia",
    "hawaii": "Hawaii",
    "illinois": "Illinois",
    "indiana": "Indiana",
    "massachusetts": "Massachusetts",
    "missouri": "Missouri",
    "new york": "New York",
    "tennessee": "Tennessee",
    "virginia": "Virginia",
    "washington": "Washington",
}


STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "for",
    "with",
    "find",
    "me",
    "show",
    "of",
    "in",
    "to",
    "on",
    "bill",
    "bills",
    "similar",
    "related",
    "conflicting",
    "conflict",
    "ones",
    "ones.",
}


def normalize_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9-]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def expand_terms(query: str, filters: SearchFilters) -> list[str]:
    tokens = normalize_tokens(query)
    expanded = list(tokens)
    if filters.topic and filters.topic.lower() in settings.topic_expansions:
        expanded.extend(settings.topic_expansions[filters.topic.lower()])
    for token in tokens:
        expanded.extend(settings.topic_expansions.get(token, []))
        expanded.extend(settings.concept_expansions.get(token, []))
    return list(dict.fromkeys(expanded))


def build_match_query(query: str, filters: SearchFilters) -> str:
    unique = expand_terms(query, filters)
    if not unique:
        unique = [query.strip()]
    return " OR ".join(f'"{token}"' if " " in token else token for token in unique[:12])


def infer_filters(query: str, filters: SearchFilters) -> SearchFilters:
    lowered = query.lower()
    updates: dict[str, str] = {}
    if not filters.jurisdiction:
        for state_key, jurisdiction in STATE_BY_NAME.items():
            if state_key in lowered:
                updates["jurisdiction"] = jurisdiction
                break
    if not filters.topic:
        for topic, terms in settings.topic_expansions.items():
            candidates = [topic, *terms]
            if any(term in lowered for term in candidates):
                updates["topic"] = topic
                break
    return filters.model_copy(update=updates) if updates else filters


def text_blob(item: dict[str, Any]) -> str:
    return " ".join(
        [
            item.get("identifier", ""),
            item.get("title", ""),
            item.get("summary", ""),
            item.get("sponsor", ""),
            item.get("committee", ""),
            " ".join(item.get("topics", [])),
        ]
    ).lower()


def match_coverage(item: dict[str, Any], terms: list[str]) -> tuple[int, int]:
    if not terms:
        return 0, 0
    blob = text_blob(item)
    matched = 0
    for term in terms:
        if term.lower() in blob:
            matched += 1
    return matched, len(terms)


def phrase_match_score(item: dict[str, Any], query: str) -> float:
    lowered_query = query.strip().lower()
    if not lowered_query:
        return 0.0
    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    identifier = item.get("identifier", "").lower()
    if lowered_query == identifier:
        return 20.0
    if lowered_query in title:
        return 14.0
    if lowered_query in summary:
        return 10.0
    return 0.0


def recency_score(item: dict[str, Any]) -> float:
    raw_date = item.get("latest_action_date")
    if not raw_date:
        return 0.0
    try:
        action_date = date.fromisoformat(str(raw_date))
    except ValueError:
        return 0.0
    age_days = max((date.today() - action_date).days, 0)
    freshness = max(0.0, 365.0 - min(age_days, 365)) / 365.0
    return freshness * 20.0


def ranking_key(item: dict[str, Any], score: float, sort_mode: str) -> tuple[object, ...]:
    latest_action_date = item.get("latest_action_date") or ""
    if sort_mode == "recent":
        return (latest_action_date, score, item.get("identifier", ""))
    return (score, latest_action_date, item.get("identifier", ""))


def search_bills(query: str, filters: SearchFilters) -> SearchResponse:
    effective_filters = infer_filters(query, filters)
    match_query = build_match_query(query, effective_filters)
    exact_hits = bills.search_exact(query, limit=min(filters.limit, 10))
    lexical_hits = bills.search_fts(
        match_query,
        limit=max(filters.limit * 4, 30),
        filters={
            "jurisdiction": effective_filters.jurisdiction,
            "session_name": effective_filters.session,
            "status": effective_filters.status,
            "outcome": effective_filters.outcome,
            "topic": effective_filters.topic,
        },
    )
    fallback_used = False
    if not lexical_hits and effective_filters != filters:
        effective_filters = filters
        match_query = build_match_query(query, effective_filters)
        lexical_hits = bills.search_fts(
            match_query,
            limit=max(filters.limit * 4, 30),
            filters={
                "jurisdiction": effective_filters.jurisdiction,
                "session_name": effective_filters.session,
                "status": effective_filters.status,
                "outcome": effective_filters.outcome,
                "topic": effective_filters.topic,
            },
        )
        fallback_used = True

    candidate_scores: dict[str, float] = defaultdict(float)
    candidate_payloads: dict[str, dict[str, Any]] = {}
    candidate_reasons: dict[str, list[str]] = defaultdict(list)
    query_tokens = normalize_tokens(query)
    expanded_terms = expand_terms(query, effective_filters)

    for item in exact_hits:
        candidate_payloads[item["bill_id"]] = item
        candidate_scores[item["bill_id"]] += 40.0
        candidate_reasons[item["bill_id"]].append("Exact identifier or phrase match")

    for item in lexical_hits:
        candidate_payloads[item["bill_id"]] = item
        candidate_scores[item["bill_id"]] += float(item.get("score", 0.0)) * settings.lexical_weight
        overlap = len(set(query_tokens) & set(normalize_tokens(" ".join([item["title"], item["summary"]]))))
        if overlap:
            candidate_scores[item["bill_id"]] += overlap * 3.0
            candidate_reasons[item["bill_id"]].append(f"{overlap} keyword overlap signals")
        if effective_filters.topic and effective_filters.topic in item["topics"]:
            candidate_scores[item["bill_id"]] += 5.0
            candidate_reasons[item["bill_id"]].append(f"Topic filter matched {effective_filters.topic}")
        if effective_filters.jurisdiction and item["jurisdiction"] == effective_filters.jurisdiction:
            candidate_scores[item["bill_id"]] += 10.0
            candidate_reasons[item["bill_id"]].append(f"Jurisdiction matched {effective_filters.jurisdiction}")
        matched_terms, total_terms = match_coverage(item, expanded_terms)
        if matched_terms:
            coverage_score = (matched_terms / total_terms) * 24.0
            candidate_scores[item["bill_id"]] += coverage_score
            candidate_reasons[item["bill_id"]].append(f"Matched {matched_terms} of {total_terms} retrieval terms")
        exact_phrase_score = phrase_match_score(item, query)
        if exact_phrase_score:
            candidate_scores[item["bill_id"]] += exact_phrase_score
            candidate_reasons[item["bill_id"]].append("Direct phrase alignment")
        if filters.sort == "recent":
            freshness = recency_score(item)
            if freshness:
                candidate_scores[item["bill_id"]] += freshness
                candidate_reasons[item["bill_id"]].append("Recent legislative activity")

    semantic_vector = embed_text(query)
    if semantic_vector:
        vector_map = dict(bills.list_bill_vectors())
        for bill_id, vector in vector_map.items():
            similarity = bills.cosine_similarity(semantic_vector, vector)
            if similarity <= 0:
                continue
            if bill_id not in candidate_payloads:
                detail = bills.get_bill(bill_id)
                if not detail:
                    continue
                candidate_payloads[bill_id] = detail
            candidate_scores[bill_id] += similarity * 100.0 * settings.semantic_weight
            candidate_reasons[bill_id].append("Embedding similarity boost")

    ranked_items = sorted(
        candidate_payloads.values(),
        key=lambda item: ranking_key(item, candidate_scores[item["bill_id"]], filters.sort),
        reverse=True,
    )[: filters.limit]

    response_items = [
        BillListItem(
            bill_id=item["bill_id"],
            identifier=item["identifier"],
            jurisdiction=item["jurisdiction"],
            state_code=item["state_code"],
            title=item["title"],
            summary=item["summary"],
            status=item["status"],
            outcome=item["outcome"],
            sponsor=item["sponsor"],
            committee=item["committee"],
            session_name=item["session_name"],
            source_url=item.get("source_url"),
            topics=item["topics"],
            matched_reasons=list(dict.fromkeys(candidate_reasons[item["bill_id"]]))[:3] or ["Lexical relevance match"],
            relevance_score=round(candidate_scores[item["bill_id"]], 2),
        )
        for item in ranked_items
    ]

    return SearchResponse(
        mode="standard",
        query=query,
        explanation="Standard search combines exact matching, BM25-style full-text search, filter narrowing, and optional embeddings when vectors are available.",
        plan={
            "match_query": match_query,
            "used_embeddings": semantic_vector is not None,
            "effective_filters": effective_filters.model_dump(),
            "fallback_used": fallback_used,
        },
        items=response_items,
    )
