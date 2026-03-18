from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from clause_backend.schemas import LawListItem, LawSearchFilters, LawSearchResponse
from clause_backend.services.gemini import gemini_available, generate_json, rerank_candidates
from clause_backend.services.law_search import expand_law_terms, infer_law_filters, search_laws
from clause_backend.services.standard_search import normalize_tokens


def heuristic_plan(query: str, filters: LawSearchFilters) -> dict[str, Any]:
    lowered = query.lower()
    intent = "find-related-laws"
    if "conflict" in lowered or "contradict" in lowered or "preempt" in lowered:
        intent = "find-conflicting-laws"
    elif "similar" in lowered:
        intent = "find-similar-laws"
    elif "section" in lowered or "cite" in lowered:
        intent = "find-exact-law"

    rewrites = [query]
    cleaned = re.sub(r"\b(find|me|which|law|laws|section|sections)\b", " ", lowered)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned and cleaned != lowered:
        rewrites.append(cleaned)
    if intent == "find-conflicting-laws":
        rewrites.append(f"{cleaned} conflicting statute".strip())
        rewrites.append(f"{cleaned} preemption".strip())
    elif intent == "find-similar-laws":
        rewrites.append(f"{cleaned} related statute".strip())
        rewrites.append(f"{cleaned} same policy".strip())
    else:
        rewrites.append(f"{cleaned} statute".strip())

    return {
        "intent": intent,
        "rewrites": [item for item in dict.fromkeys(rewrites) if item],
        "filters": filters.model_dump(),
        "used_gemini": False,
    }


def gemini_plan(query: str, filters: LawSearchFilters) -> dict[str, Any] | None:
    payload = generate_json(
        f"""
You are planning legal retrieval for a law search system.
Return JSON only with keys:
- intent
- rewrites
- filters

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


def agentic_law_search(query: str, filters: LawSearchFilters) -> LawSearchResponse:
    plan = gemini_plan(query, filters) if gemini_available() else None
    if not plan:
        plan = heuristic_plan(query, filters)

    rewrites = [item for item in plan.get("rewrites", []) if isinstance(item, str) and item.strip()]
    if not rewrites:
        rewrites = [query]

    effective_filters = infer_law_filters(query, filters)
    plan_filters = plan.get("filters")
    if isinstance(plan_filters, dict):
        jurisdiction = plan_filters.get("jurisdiction")
        source = plan_filters.get("source")
        updates: dict[str, str] = {}
        if isinstance(jurisdiction, str) and jurisdiction in {"California", "United States"}:
            updates["jurisdiction"] = jurisdiction
        if isinstance(source, str) and source in {"California Code", "United States Code"}:
            updates["source"] = source
        if updates:
            effective_filters = effective_filters.model_copy(update=updates)
    candidate_scores: dict[str, float] = defaultdict(float)
    candidate_reasons: dict[str, list[str]] = defaultdict(list)
    candidate_items: dict[str, LawListItem] = {}
    required_terms = set(normalize_tokens(query))
    broadened_scope = False

    def collect(search_filters: LawSearchFilters) -> None:
        for index, rewrite in enumerate(rewrites[:5]):
            response = search_laws(rewrite, search_filters)
            weight = max(1.0, 1.75 - index * 0.2)
            for item in response.items:
                candidate_items[item.document_id] = item
                candidate_scores[item.document_id] += item.relevance_score * weight
                candidate_reasons[item.document_id].append(f"Matched rewrite: {rewrite}")
                candidate_reasons[item.document_id].extend(item.matched_reasons)

    collect(effective_filters)
    if effective_filters.jurisdiction and len(candidate_items) < 2:
        broadened_scope = True
        collect(filters)

    expanded_terms = set(expand_law_terms(query))
    disqualified: set[str] = set()
    intent = str(plan.get("intent") or "")

    for document_id, item in candidate_items.items():
        item_tokens = set(normalize_tokens(" ".join([item.citation, item.heading or "", item.body_excerpt or ""])))
        overlap = len(required_terms & item_tokens)
        if overlap:
            candidate_scores[document_id] += overlap * 6.0
            candidate_reasons[document_id].append(f"{overlap} core legal terms aligned")
        elif required_terms:
            disqualified.add(document_id)
            continue
        expanded_overlap = len(expanded_terms & item_tokens)
        if expanded_overlap:
            candidate_scores[document_id] += expanded_overlap * 3.0
            candidate_reasons[document_id].append(f"{expanded_overlap} expanded terms aligned")
        if intent == "find-conflicting-laws" and any(token in item_tokens for token in {"prohibit", "unlawful", "notwithstanding", "preempt"}):
            candidate_scores[document_id] += 10.0
            candidate_reasons[document_id].append("Conflict-oriented statutory language present")

    reranked = rerank_candidates(
        query,
        intent,
        [
            {
                "id": item.document_id,
                "citation": item.citation,
                "jurisdiction": item.jurisdiction,
                "source": item.source,
                "heading": item.heading,
                "excerpt": item.body_excerpt,
            }
            for item in list(candidate_items.values())[:8]
            if item.document_id not in disqualified
        ],
    )
    if reranked:
        for document_id, result in reranked.items():
            if document_id not in candidate_items:
                continue
            candidate_scores[document_id] += float(result["score"]) * 4.0
            candidate_reasons[document_id].append(str(result["reason"]))

    ranked_items = sorted(
        [item for item in candidate_items.values() if item.document_id not in disqualified],
        key=lambda item: candidate_scores[item.document_id],
        reverse=True,
    )[: filters.limit]

    explanation = "Agentic law search planned rewrites, ran repeated statute retrieval passes, and reranked candidates against the legal intent."
    if plan.get("used_gemini"):
        explanation = "Agentic law search used Gemini to plan rewrites and rerank the strongest statute candidates."
    if broadened_scope:
        explanation += " The first pass was too narrow, so the search widened beyond the inferred jurisdiction."

    return LawSearchResponse(
        mode="agentic",
        query=query,
        explanation=explanation,
        plan={**plan, "effective_filters": effective_filters.model_dump(), "broadened_scope": broadened_scope},
        items=[
            item.model_copy(
                update={
                    "relevance_score": round(candidate_scores[item.document_id], 2),
                    "matched_reasons": list(dict.fromkeys(candidate_reasons[item.document_id]))[:5],
                }
            )
            for item in ranked_items
        ],
    )
