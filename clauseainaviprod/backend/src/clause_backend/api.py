from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException

from clause_backend.repositories import app_state
from clause_backend.repositories.bills import database_stats, get_bill, list_filter_options
from clause_backend.schemas import (
    AuthConfigResponse,
    BillDetail,
    ChatRequest,
    ChatResponse,
    CreateProjectRequest,
    LawDetail,
    LawFilterOptions,
    LawSearchRequest,
    LawSearchResponse,
    LawStatsResponse,
    LoginRequest,
    LoginResponse,
    ProjectDetail,
    ProjectListItem,
    RefreshInsightsResponse,
    SearchRequest,
    SearchResponse,
    StatsResponse,
    UpdateProjectRequest,
    UserResponse,
)
from clause_backend.services.auth_service import auth_config, current_user, login, logout
from clause_backend.services.agentic_law_search import agentic_law_search
from clause_backend.services.agentic_search import agentic_search
from clause_backend.services.law_search import get_law_detail, law_filter_options, law_stats, search_laws
from clause_backend.services.project_workspace import agent_chat, refresh_project_insights
from clause_backend.services.standard_search import search_bills


router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/auth/config", response_model=AuthConfigResponse)
def get_auth_config() -> AuthConfigResponse:
    return AuthConfigResponse(**auth_config())


@router.post("/auth/login", response_model=LoginResponse)
def login_endpoint(request: LoginRequest) -> LoginResponse:
    payload = login(request.email, request.password)
    return LoginResponse(
        token=str(payload["token"]),
        user=UserResponse(**payload["user"]),
    )


@router.get("/auth/me", response_model=UserResponse)
def me(user: dict[str, object] = Depends(current_user)) -> UserResponse:
    return UserResponse(**user)


@router.post("/auth/logout")
def logout_endpoint(authorization: str | None = Header(default=None)) -> dict[str, bool]:
    return logout(authorization)


@router.get("/stats", response_model=StatsResponse)
def stats(_: dict[str, object] = Depends(current_user)) -> StatsResponse:
    return StatsResponse(**database_stats())


@router.get("/filters")
def filters(_: dict[str, object] = Depends(current_user)) -> dict[str, list[str]]:
    return list_filter_options()


@router.get("/laws/filters", response_model=LawFilterOptions)
def laws_filters(_: dict[str, object] = Depends(current_user)) -> LawFilterOptions:
    return law_filter_options()


@router.get("/bills/{bill_id:path}", response_model=BillDetail)
def bill_detail(bill_id: str, _: dict[str, object] = Depends(current_user)) -> BillDetail:
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


@router.get("/laws/stats", response_model=LawStatsResponse)
def laws_stats(_: dict[str, object] = Depends(current_user)) -> LawStatsResponse:
    return law_stats()


@router.get("/laws/{document_id}", response_model=LawDetail)
def law_detail(document_id: str, _: dict[str, object] = Depends(current_user)) -> LawDetail:
    item = get_law_detail(document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Law not found")
    return item


@router.post("/search/standard", response_model=SearchResponse)
def standard_search(request: SearchRequest, _: dict[str, object] = Depends(current_user)) -> SearchResponse:
    return search_bills(request.query, request.filters)


@router.post("/search/agentic", response_model=SearchResponse)
def agentic_search_endpoint(request: SearchRequest, _: dict[str, object] = Depends(current_user)) -> SearchResponse:
    return agentic_search(request.query, request.filters)


@router.post("/laws/search/standard", response_model=LawSearchResponse)
def standard_law_search(request: LawSearchRequest, _: dict[str, object] = Depends(current_user)) -> LawSearchResponse:
    return search_laws(request.query, request.filters)


@router.post("/laws/search/agentic", response_model=LawSearchResponse)
def agentic_law_search_endpoint(request: LawSearchRequest, _: dict[str, object] = Depends(current_user)) -> LawSearchResponse:
    return agentic_law_search(request.query, request.filters)


def _project_detail_or_404(project_id: str, owner_user_id: str) -> dict[str, object]:
    project = app_state.get_project(project_id, owner_user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _serialize_project_detail(project: dict[str, object]) -> ProjectDetail:
    insights = app_state.list_project_insights(str(project["project_id"]))
    messages = app_state.list_project_messages(str(project["project_id"]))
    return ProjectDetail(
        project_id=str(project["project_id"]),
        title=str(project["title"]),
        policy_goal=str(project["policy_goal"]),
        jurisdiction=project.get("jurisdiction"),
        status=str(project["status"]),
        stage=str(project["stage"]),
        summary=str(project["summary"]),
        bill_text=str(project["bill_text"]),
        created_at=str(project["created_at"]),
        updated_at=str(project["updated_at"]),
        insights=insights,
        messages=messages,
    )


@router.get("/projects", response_model=list[ProjectListItem])
def list_projects(user: dict[str, object] = Depends(current_user)) -> list[ProjectListItem]:
    rows = app_state.list_projects(str(user["user_id"]))
    return [
        ProjectListItem(
            project_id=str(row["project_id"]),
            title=str(row["title"]),
            policy_goal=str(row["policy_goal"]),
            jurisdiction=row.get("jurisdiction"),
            status=str(row["status"]),
            stage=str(row["stage"]),
            summary=str(row["summary"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
        for row in rows
    ]


@router.post("/projects", response_model=ProjectDetail)
def create_project(request: CreateProjectRequest, user: dict[str, object] = Depends(current_user)) -> ProjectDetail:
    project = app_state.create_project(str(user["user_id"]), request.title, request.policy_goal, request.jurisdiction)
    return _serialize_project_detail(project)


@router.get("/projects/{project_id}", response_model=ProjectDetail)
def get_project(project_id: str, user: dict[str, object] = Depends(current_user)) -> ProjectDetail:
    project = _project_detail_or_404(project_id, str(user["user_id"]))
    return _serialize_project_detail(project)


@router.put("/projects/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    user: dict[str, object] = Depends(current_user),
) -> ProjectDetail:
    project = app_state.update_project(
        project_id,
        str(user["user_id"]),
        request.model_dump(exclude_none=True),
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _serialize_project_detail(project)


@router.post("/projects/{project_id}/insights/refresh", response_model=RefreshInsightsResponse)
def refresh_project(
    project_id: str,
    user: dict[str, object] = Depends(current_user),
) -> RefreshInsightsResponse:
    project = _project_detail_or_404(project_id, str(user["user_id"]))
    payload = refresh_project_insights(project)
    return RefreshInsightsResponse(**payload)


@router.post("/projects/{project_id}/agent", response_model=ChatResponse)
def project_agent_chat(
    project_id: str,
    request: ChatRequest,
    user: dict[str, object] = Depends(current_user),
) -> ChatResponse:
    project = _project_detail_or_404(project_id, str(user["user_id"]))
    app_state.add_project_message(project_id, "user", request.message, [])
    payload = agent_chat(project, request.message)
    return ChatResponse(**payload)
