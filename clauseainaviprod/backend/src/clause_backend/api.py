from __future__ import annotations

from fastapi import APIRouter, HTTPException

from clause_backend.repositories.bills import database_stats, get_bill, list_filter_options
from clause_backend.schemas import BillDetail, SearchRequest, SearchResponse, StatsResponse
from clause_backend.services.agentic_search import agentic_search
from clause_backend.services.standard_search import search_bills


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    return StatsResponse(**database_stats())


@router.get("/filters")
def filters() -> dict[str, list[str]]:
    return list_filter_options()


@router.get("/bills/{bill_id}", response_model=BillDetail)
def bill_detail(bill_id: str) -> BillDetail:
    item = get_bill(bill_id)
    if not item:
        raise HTTPException(status_code=404, detail="Bill not found")
    return BillDetail(
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
        matched_reasons=[],
        relevance_score=0.0,
        full_text=item["full_text"],
        latest_action_date=item.get("latest_action_date"),
    )


@router.post("/search/standard", response_model=SearchResponse)
def standard_search(request: SearchRequest) -> SearchResponse:
    return search_bills(request.query, request.filters)


@router.post("/search/agentic", response_model=SearchResponse)
def agentic_search_endpoint(request: SearchRequest) -> SearchResponse:
    return agentic_search(request.query, request.filters)

