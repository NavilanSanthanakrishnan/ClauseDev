from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from clause_backend.schemas import BillListItem, SearchFilters, SearchResponse
from clause_backend.services.gemini import generate_json, gemini_available, rerank_candidates
from clause_backend.services.standard_search import expand_terms, infer_filters, normalize_tokens, search_bills


STATE_BY_NAME = {
    "alabama": "Alabama",
    "california": "California",
    "colorado": "Colorado",
    "georgia": "Georgia",
    "hawaii": "Hawaii",
    "illinois": "Illinois",
    "massachusetts": "Massachusetts",
    "new york": "New York",
    "washington": "Washington",
}


def heuristic_plan(query: str, filters: SearchFilters) -> dict[str, Any]:
    lowered = query.lower()
    intent = "find-similar"
    if "conflict" in lowered or "opposite" in lowered:
        intent = "find-conflicts"
    elif "compare" in lowered:
        intent = "compare"
    elif "similar" in lowered:
        intent = "find-similar"

    jurisdictions = [name for key, name in STATE_BY_NAME.items() if key in lowered]
    rewrites = [query]
    cleaned = re.sub(r"\b(find|show|me|similar|conflicting|ones|bills)\b", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned and cleaned != lowered:
        rewrites.append(cleaned)

    if intent == "find-conflicts":
        rewrites.append(f"{cleaned} alternative policy approach".strip())
        rewrites.append(f"{cleaned} opposite outcome".strip())
    else:
        rewrites.append(f"{cleaned} related legislation".strip())
        rewrites.append(f"{cleaned} policy pattern".strip())

    return {
        "intent": intent,
        "jurisdictions": jurisdictions,
        "rewrites": [item for item in dict.fromkeys(rewrites) if item],
        "filters": filters.model_dump(),
        "ranking_focus": "Prefer evidence-dense bills with matching jurisdictions, topics, and policy language.",
        "used_gemini": False,
    }


def query_needs_gemini_planning(query: str) -> bool:
    lowered = query.lower()
    if any(token in lowered for token in ('"', "'", "\n", "section", "contradict", "conflict", "compare", "draft")):
        return True
    return len(normalize_tokens(query)) >= 10


def gemini_plan(query: str, filters: SearchFilters) -> dict[str, Any] | None:
    payload = generate_json(
        f"""
You are planning bill retrieval for a legislative search system.
Return JSON only with keys:
- intent
- jurisdictions
- rewrites
- filters
- ranking_focus

User query:
{query}

Current filters:
{filters.model_dump_json(indent=2)}
        """.strip()
    )
    if not payload:
        return None
    payload["used_gemini"] = True
    return payload


def rerank_agentic(query: str, plan: dict[str, Any], filters: SearchFilters) -> SearchResponse:
    rewrites = [item for item in plan.get("rewrites", []) if isinstance(item, str) and item.strip()]
    if not rewrites:
        rewrites = [query]
    effective_filters = infer_filters(query, filters)
    jurisdictions = [item for item in plan.get("jurisdictions", []) if isinstance(item, str)]
    if not effective_filters.jurisdiction and len(jurisdictions) == 1:
        effective_filters = effective_filters.model_copy(update={"jurisdiction": jurisdictions[0]})

    candidate_scores: dict[str, float] = defaultdict(float)
    candidate_reasons: dict[str, list[str]] = defaultdict(list)
    candidate_items: dict[str, BillListItem] = {}
    disqualified: set[str] = set()
    broadened_scope = False
    rewrite_weights = {rewrite: max(1.0, 1.75 - index * 0.2) for index, rewrite in enumerate(rewrites[:5])}
    expanded_terms = set(expand_terms(query, effective_filters))
    jurisdiction_terms = set(normalize_tokens(effective_filters.jurisdiction or ""))
    required_terms = {term for term in normalize_tokens(query) if term not in jurisdiction_terms}
    loop_trace: list[dict[str, Any]] = []

    def collect(search_filters: SearchFilters) -> None:
        queued = list(rewrites[:5])
        seen: set[str] = set()
        for step_index in range(3):
            if not queued:
                break
            rewrite = queued.pop(0)
            if rewrite in seen:
                continue
            seen.add(rewrite)
            standard_response = search_bills(rewrite, search_filters.model_copy(update={"limit": max(filters.limit, 8)}))
            loop_trace.append(
                {
                    "step": step_index + 1,
                    "rewrite": rewrite,
                    "result_count": len(standard_response.items),
                    "jurisdiction": search_filters.jurisdiction,
                }
            )
            for item in standard_response.items:
                candidate_items[item.bill_id] = item
                candidate_scores[item.bill_id] += item.relevance_score * rewrite_weights.get(rewrite, 1.0)
                candidate_reasons[item.bill_id].append(f"Matched rewrite: {rewrite}")
                candidate_reasons[item.bill_id].extend(item.matched_reasons)
            if not required_terms:
                continue
            uncovered_terms = set(required_terms)
            for item in standard_response.items[:3]:
                item_tokens = set(normalize_tokens(" ".join([item.title, item.summary, item.identifier])))
                uncovered_terms -= item_tokens
            if uncovered_terms:
                follow_up = " ".join(
                    part
                    for part in [effective_filters.jurisdiction or "", *sorted(uncovered_terms)]
                    if part
                )
                if follow_up and follow_up not in seen and follow_up not in queued:
                    queued.append(follow_up)

    def best_alignment_depth() -> int:
        best = 0
        for item in candidate_items.values():
            item_tokens = set(normalize_tokens(" ".join([item.title, item.summary, item.identifier])))
            best = max(best, len(expanded_terms & item_tokens))
        return best

    collect(effective_filters)
    if effective_filters.jurisdiction and (not candidate_items or best_alignment_depth() < 2):
        broadened_scope = True
        collect(filters)

    intent = str(plan.get("intent") or "")
    query_tokens = set(normalize_tokens(query))

    for bill_id, item in candidate_items.items():
        item_tokens = set(normalize_tokens(" ".join([item.title, item.summary, item.identifier])))
        overlap = len(query_tokens & item_tokens)
        candidate_scores[bill_id] += overlap * 4.0
        if overlap:
            candidate_reasons[bill_id].append(f"{overlap} intent tokens aligned")
        required_overlap = len(required_terms & item_tokens)
        if required_overlap:
            candidate_scores[bill_id] += required_overlap * 10.0
            candidate_reasons[bill_id].append(f"{required_overlap} core policy terms aligned")
        elif required_terms:
            disqualified.add(bill_id)
            continue
        expanded_overlap = len(expanded_terms & item_tokens)
        if expanded_overlap:
            candidate_scores[bill_id] += expanded_overlap * 3.0
            candidate_reasons[bill_id].append(f"{expanded_overlap} expanded retrieval signals aligned")
        if broadened_scope and effective_filters.jurisdiction and item.jurisdiction == effective_filters.jurisdiction and required_overlap < min(2, len(required_terms) or 1):
            candidate_scores[bill_id] -= 18.0
        if intent == "find-conflicts" and item.outcome.lower() in {"failed", "vetoed"}:
            candidate_scores[bill_id] += 8.0
            candidate_reasons[bill_id].append("Conflict intent boosted contrasting outcome")
        elif intent == "find-conflicts" and item.outcome.lower() in {"passed", "enacted"}:
            candidate_scores[bill_id] -= 4.0
        elif intent == "find-similar" and item.outcome.lower() in {"passed", "enacted", "active"}:
            candidate_scores[bill_id] += 6.0
            candidate_reasons[bill_id].append("Similarity intent boosted enacted peer")

    reranked = rerank_candidates(
        query,
        intent,
        [
            {
                "id": item.bill_id,
                "identifier": item.identifier,
                "jurisdiction": item.jurisdiction,
                "title": item.title,
                "summary": item.summary,
                "outcome": item.outcome,
                "topics": item.topics,
            }
            for item in list(candidate_items.values())[:8]
            if item.bill_id not in disqualified
        ],
    )
    if reranked:
        for bill_id, result in reranked.items():
            if bill_id not in candidate_items:
                continue
            candidate_scores[bill_id] += float(result["score"]) * 3.5
            candidate_reasons[bill_id].append(str(result["reason"]))

    ranked_items = sorted(
        [item for item in candidate_items.values() if item.bill_id not in disqualified],
        key=lambda item: candidate_scores[item.bill_id],
        reverse=True,
    )[: filters.limit]

    response_items = [
        item.model_copy(
            update={
                "relevance_score": round(candidate_scores[item.bill_id], 2),
                "matched_reasons": list(dict.fromkeys(candidate_reasons[item.bill_id]))[:4],
            }
        )
        for item in ranked_items
    ]

    explanation = "Agentic search planned multiple rewrites, ran repeated retrieval passes, and reranked candidates against the search intent."
    if plan.get("used_gemini"):
        explanation = "Agentic search used Gemini to plan retrieval rewrites, then reranked evidence-backed candidates."
    if broadened_scope:
        explanation += " The first pass found no results in the inferred jurisdiction, so the search widened to cross-jurisdiction peers."

    return SearchResponse(
        mode="agentic",
        query=query,
        explanation=explanation,
        plan={
            **plan,
            "effective_filters": effective_filters.model_dump(),
            "broadened_scope": broadened_scope,
            "loop_trace": loop_trace,
        },
        items=response_items,
    )


def agentic_search(query: str, filters: SearchFilters) -> SearchResponse:
    plan = gemini_plan(query, filters) if gemini_available() and query_needs_gemini_planning(query) else None
    if not plan:
        plan = heuristic_plan(query, filters)
    return rerank_agentic(query, plan, filters)
