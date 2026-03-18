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


class LawSearchFilters(BaseModel):
    jurisdiction: str | None = None
    source: str | None = None
    sort: SortMode = "relevance"
    limit: int = Field(default=12, ge=1, le=50)


class LawSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    filters: LawSearchFilters = Field(default_factory=LawSearchFilters)


class LawListItem(BaseModel):
    document_id: str
    citation: str
    jurisdiction: str
    source: str
    heading: str | None = None
    hierarchy_path: str | None = None
    body_excerpt: str | None = None
    source_url: str | None = None
    matched_reasons: list[str]
    relevance_score: float


class LawSearchResponse(BaseModel):
    mode: SearchMode
    query: str
    explanation: str
    plan: dict[str, object]
    items: list[LawListItem]


class LawDetail(LawListItem):
    body_text: str


class LawStatsResponse(BaseModel):
    total_laws: int
    california_laws: int
    federal_laws: int


class LawFilterOptions(BaseModel):
    jurisdictions: list[str]
    sources: list[str]


class AuthConfigResponse(BaseModel):
    enabled: bool


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=3, max_length=255)


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


class ProjectListItem(BaseModel):
    project_id: str
    title: str
    policy_goal: str
    jurisdiction: str | None = None
    status: str
    stage: str
    summary: str
    updated_at: str
    created_at: str


class ProjectDetail(ProjectListItem):
    bill_text: str
    insights: dict[str, object] = Field(default_factory=dict)
    messages: list[dict[str, object]] = Field(default_factory=list)


class CreateProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    policy_goal: str = Field(min_length=1, max_length=1000)
    jurisdiction: str | None = Field(default=None, max_length=255)


class UpdateProjectRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    policy_goal: str | None = Field(default=None, max_length=1000)
    jurisdiction: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, max_length=255)
    stage: str | None = Field(default=None, max_length=255)
    summary: str | None = Field(default=None, max_length=4000)
    bill_text: str | None = None


class RefreshInsightsResponse(BaseModel):
    similar_bills: dict[str, object]
    conflicting_laws: dict[str, object]
    stakeholders: dict[str, object]
    drafting_focus: dict[str, object]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    message: dict[str, object]
    tool_trace: list[dict[str, object]]
    suggested_stage: str | None = None
    suggested_status: str | None = None
    revision_excerpt: str | None = None
