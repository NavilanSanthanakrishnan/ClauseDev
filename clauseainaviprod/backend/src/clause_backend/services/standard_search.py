from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from typing import Any

from clause_backend.repositories import bills
from clause_backend.schemas import BillListItem, SearchFilters, SearchResponse

STATE_BY_NAME = {
    "alabama": "Alabama",
    "alaska": "Alaska",
    "arizona": "Arizona",
    "arkansas": "Arkansas",
    "california": "California",
    "colorado": "Colorado",
    "connecticut": "Connecticut",
    "delaware": "Delaware",
    "district of columbia": "District of Columbia",
    "florida": "Florida",
    "georgia": "Georgia",
    "hawaii": "Hawaii",
    "idaho": "Idaho",
    "iowa": "Iowa",
    "illinois": "Illinois",
    "indiana": "Indiana",
    "kansas": "Kansas",
    "kentucky": "Kentucky",
    "louisiana": "Louisiana",
    "maine": "Maine",
    "maryland": "Maryland",
    "massachusetts": "Massachusetts",
    "michigan": "Michigan",
    "minnesota": "Minnesota",
    "mississippi": "Mississippi",
    "missouri": "Missouri",
    "montana": "Montana",
    "nebraska": "Nebraska",
    "nevada": "Nevada",
    "new hampshire": "New Hampshire",
    "new jersey": "New Jersey",
    "new mexico": "New Mexico",
    "new york": "New York",
    "north carolina": "North Carolina",
    "north dakota": "North Dakota",
    "ohio": "Ohio",
    "oklahoma": "Oklahoma",
    "oregon": "Oregon",
    "pennsylvania": "Pennsylvania",
    "rhode island": "Rhode Island",
    "south carolina": "South Carolina",
    "south dakota": "South Dakota",
    "tennessee": "Tennessee",
    "texas": "Texas",
    "utah": "Utah",
    "vermont": "Vermont",
    "virginia": "Virginia",
    "west virginia": "West Virginia",
    "wisconsin": "Wisconsin",
    "wyoming": "Wyoming",
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
    "ones",
    "ones.",
}


def normalize_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9-]+", text.lower())
    return [
        token
        for token in tokens
        if token not in STOPWORDS and (len(token) > 1 or token.isdigit())
    ]


def normalize_identifier_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def expand_terms(query: str, filters: SearchFilters) -> list[str]:
    del filters
    return normalize_tokens(query)


def is_identifier_like(query: str) -> bool:
    normalized = query.strip()
    return bool(re.search(r"[A-Za-z]", normalized) and re.search(r"\d", normalized))


def build_match_query(query: str, operator: str = "OR") -> str:
    unique = normalize_tokens(query)
    if not unique:
        unique = [query.strip()]

    def escape(token: str) -> str:
        return f"\"{token.replace('\"', '\"\"')}\""

    delimiter = f" {operator} "
    return delimiter.join(escape(token) for token in unique[:12] if token.strip())


def infer_filters(query: str, filters: SearchFilters) -> SearchFilters:
    lowered = query.lower()
    updates: dict[str, str] = {}
    if not filters.jurisdiction:
        for state_key, jurisdiction in sorted(STATE_BY_NAME.items(), key=lambda item: len(item[0]), reverse=True):
            if re.search(rf"\b{re.escape(state_key)}\b", lowered):
                updates["jurisdiction"] = jurisdiction
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


def identifier_match_score(item: dict[str, Any], query: str) -> float:
    query_identifier = normalize_identifier_text(query)
    candidate_identifier = normalize_identifier_text(item.get("identifier", ""))
    if not query_identifier or not candidate_identifier:
        return 0.0
    if query_identifier == candidate_identifier:
        return 800.0
    if candidate_identifier.startswith(query_identifier):
        return 120.0
    return 0.0


def phrase_match_score(item: dict[str, Any], query: str) -> float:
    lowered_query = query.strip().lower()
    if not lowered_query:
        return 0.0
    title = item.get("title", "").lower()
    summary = item.get("summary", "").lower()
    identifier = item.get("identifier", "").lower()
    if lowered_query == identifier:
        return 120.0
    if lowered_query == title:
        return 90.0
    if lowered_query == summary:
        return 70.0
    if lowered_query in title:
        return 30.0
    if lowered_query in summary:
        return 18.0
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
    strict_match_query = build_match_query(query, "AND")
    broad_match_query = build_match_query(query, "OR")
    exact_hits = bills.search_exact(query, limit=min(filters.limit, 10))
    strict_hits = bills.search_fts(
        strict_match_query,
        limit=max(filters.limit * 4, 30),
        filters={
            "jurisdiction": effective_filters.jurisdiction,
            "session_name": effective_filters.session,
            "status": effective_filters.status,
            "outcome": effective_filters.outcome,
            "topic": effective_filters.topic,
        },
    )
    broad_hits = bills.search_fts(
        broad_match_query,
        limit=max(filters.limit * 6, 40),
        filters={
            "jurisdiction": effective_filters.jurisdiction,
            "session_name": effective_filters.session,
            "status": effective_filters.status,
            "outcome": effective_filters.outcome,
            "topic": effective_filters.topic,
        },
    )
    fallback_used = False
    if not strict_hits and not broad_hits and effective_filters != filters:
        effective_filters = filters
        strict_match_query = build_match_query(query, "AND")
        broad_match_query = build_match_query(query, "OR")
        strict_hits = bills.search_fts(
            strict_match_query,
            limit=max(filters.limit * 4, 30),
            filters={
                "jurisdiction": effective_filters.jurisdiction,
                "session_name": effective_filters.session,
                "status": effective_filters.status,
                "outcome": effective_filters.outcome,
                "topic": effective_filters.topic,
            },
        )
        broad_hits = bills.search_fts(
            broad_match_query,
            limit=max(filters.limit * 6, 40),
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
    identifier_query = is_identifier_like(query)

    for item in exact_hits:
        candidate_payloads[item["bill_id"]] = item
        candidate_scores[item["bill_id"]] += 180.0
        candidate_reasons[item["bill_id"]].append("Direct exact match")

    for source_label, hit_weight, hit_set in (
        ("strict lexical search", 1.35, strict_hits),
        ("broad lexical search", 1.0, broad_hits),
    ):
        for item in hit_set:
            candidate_payloads[item["bill_id"]] = item
            candidate_scores[item["bill_id"]] += float(item.get("score", 0.0)) * hit_weight
            candidate_reasons[item["bill_id"]].append(f"Retrieved by {source_label}")

    for item in candidate_payloads.values():
        candidate_payloads[item["bill_id"]] = item
        overlap = len(set(query_tokens) & set(normalize_tokens(" ".join([item["title"], item["summary"], item["identifier"]]))))
        if overlap:
            candidate_scores[item["bill_id"]] += overlap * 10.0
            candidate_reasons[item["bill_id"]].append(f"{overlap} keyword overlap signals")
        if effective_filters.topic and effective_filters.topic in item["topics"]:
            candidate_scores[item["bill_id"]] += 5.0
            candidate_reasons[item["bill_id"]].append(f"Topic filter matched {effective_filters.topic}")
        if effective_filters.jurisdiction and item["jurisdiction"] == effective_filters.jurisdiction:
            candidate_scores[item["bill_id"]] += 10.0
            candidate_reasons[item["bill_id"]].append(f"Jurisdiction matched {effective_filters.jurisdiction}")
        matched_terms, total_terms = match_coverage(item, query_tokens)
        if matched_terms:
            coverage_score = (matched_terms / total_terms) * 36.0
            candidate_scores[item["bill_id"]] += coverage_score
            candidate_reasons[item["bill_id"]].append(f"Matched {matched_terms} of {total_terms} retrieval terms")
        exact_phrase_score = phrase_match_score(item, query)
        if exact_phrase_score:
            candidate_scores[item["bill_id"]] += exact_phrase_score
            candidate_reasons[item["bill_id"]].append("Direct phrase alignment")
        identifier_score = identifier_match_score(item, query)
        if identifier_score:
            candidate_scores[item["bill_id"]] += identifier_score
            candidate_reasons[item["bill_id"]].append("Identifier aligned exactly")
        elif identifier_query:
            candidate_scores[item["bill_id"]] -= 90.0
        if filters.sort == "recent":
            freshness = recency_score(item)
            if freshness:
                candidate_scores[item["bill_id"]] += freshness
                candidate_reasons[item["bill_id"]].append("Recent legislative activity")

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
        explanation="Standard search combines exact matching, strict-and-broad full-text retrieval, jurisdiction inference, and deterministic reranking without model calls.",
        plan={
            "strict_match_query": strict_match_query,
            "broad_match_query": broad_match_query,
            "identifier_query": identifier_query,
            "effective_filters": effective_filters.model_dump(),
            "fallback_used": fallback_used,
        },
        items=response_items,
    )
