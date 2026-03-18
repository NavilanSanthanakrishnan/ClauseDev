from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SortMode = Literal["relevance", "recent"]
SearchMode = Literal["standard", "agentic"]


class SearchFilters(BaseModel):
    jurisdiction: str | None = None
    session: str | None = None
    status: str | None = None
    topic: str | None = None
    outcome: str | None = None
    sort: SortMode = "relevance"
    limit: int = Field(default=12, ge=1, le=50)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=240)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class BillListItem(BaseModel):
    bill_id: str
    identifier: str
    jurisdiction: str
    state_code: str
    title: str
    summary: str
    status: str
    outcome: str
    sponsor: str
    committee: str
    session_name: str
    source_url: str | None = None
    topics: list[str]
    matched_reasons: list[str]
    relevance_score: float


class SearchResponse(BaseModel):
    mode: SearchMode
    query: str
    explanation: str
    plan: dict[str, object]
    items: list[BillListItem]


class BillDetail(BillListItem):
    full_text: str
    latest_action_date: str | None = None


class StatsResponse(BaseModel):
    total_bills: int
    jurisdictions: int
    active_sessions: int
    top_topics: list[str]

