from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from clause_backend.core.config import settings
from clause_backend.repositories import bills
from clause_backend.schemas import BillListItem, SearchFilters, SearchResponse
from clause_backend.services.gemini import embed_text


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
}


def normalize_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9-]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def build_match_query(query: str, filters: SearchFilters) -> str:
    tokens = normalize_tokens(query)
    expansions = list(tokens)
    if filters.topic and filters.topic.lower() in settings.topic_expansions:
        expansions.extend(settings.topic_expansions[filters.topic.lower()])
    for token in tokens:
        expansions.extend(settings.topic_expansions.get(token, []))
    unique = list(dict.fromkeys(expansions))
    if not unique:
        unique = [query.strip()]
    return " OR ".join(f'"{token}"' if " " in token else token for token in unique[:12])


def search_bills(query: str, filters: SearchFilters) -> SearchResponse:
    match_query = build_match_query(query, filters)
    exact_hits = bills.search_exact(query, limit=min(filters.limit, 10))
    lexical_hits = bills.search_fts(
        match_query,
        limit=max(filters.limit * 4, 30),
        filters={
            "jurisdiction": filters.jurisdiction,
            "session_name": filters.session,
            "status": filters.status,
            "outcome": filters.outcome,
            "topic": filters.topic,
        },
    )

    candidate_scores: dict[str, float] = defaultdict(float)
    candidate_payloads: dict[str, dict[str, Any]] = {}
    candidate_reasons: dict[str, list[str]] = defaultdict(list)
    query_tokens = normalize_tokens(query)

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
        if filters.topic and filters.topic in item["topics"]:
            candidate_scores[item["bill_id"]] += 5.0
            candidate_reasons[item["bill_id"]].append(f"Topic filter matched {filters.topic}")

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
        key=lambda item: (
            candidate_scores[item["bill_id"]],
            item.get("latest_action_date") or "",
        ),
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
        plan={"match_query": match_query, "used_embeddings": semantic_vector is not None},
        items=response_items,
    )

