from __future__ import annotations

from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field


class UploadedBillProfile(BaseModel):
    title: str = ""
    description: str = ""
    summary: str = ""
    policy_domain: List[str] = Field(default_factory=list)
    policy_intent: str = ""
    legal_mechanisms: List[str] = Field(default_factory=list)
    affected_entities: List[str] = Field(default_factory=list)
    enforcement_mechanisms: List[str] = Field(default_factory=list)
    fiscal_elements: List[str] = Field(default_factory=list)
    bill_type_hints: List[str] = Field(default_factory=list)
    jurisdiction_hints: List[str] = Field(default_factory=list)
    search_phrases: List[str] = Field(default_factory=list)


class CandidateBill(BaseModel):
    bill_id: str
    identifier: str
    title: str
    classification: List[str] = Field(default_factory=list)
    subjects: List[str] = Field(default_factory=list)
    jurisdiction_id: str
    jurisdiction_name: str
    jurisdiction_type: str
    state_code: Optional[str] = None
    session_identifier: str
    session_name: str
    session_classification: str
    latest_action_date: Optional[str] = None
    latest_action_description: str
    latest_passage_date: Optional[str] = None
    derived_status: str
    primary_bill_url: Optional[str] = None
    searchable_titles: str = ""
    raw_text: str = ""
    excerpt: str = ""
    description: str = ""
    structured_summary: str = ""
    section_headings: List[str] = Field(default_factory=list)
    matched_queries: List[str] = Field(default_factory=list)
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    llm_score: float = 0.0
    final_score: float = 0.0
    match_reason: str = ""
    match_dimensions: List[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    filename: str
    file_type: str
    extracted_text: str = ""
    extracted_text_preview: str
    extracted_text_length: int
    profile: UploadedBillProfile
    results: List[CandidateBill]
    timings: dict[str, float]
    warnings: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    database_ready: bool
    missing_indexes: List[str] = Field(default_factory=list)


class LlmRerankItem(BaseModel):
    candidate_id: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    match_dimensions: List[str] = Field(default_factory=list)


class LlmRerankResponse(BaseModel):
    top_candidates: List[LlmRerankItem] = Field(default_factory=list)
    overall_notes: str = ""


class SearchPlanMetadata(BaseModel):
    queries: List[str]
    jurisdiction_hints: List[str]
    bill_type_hints: List[str]


class SearchRequestOptions(BaseModel):
    final_result_limit: int = Field(default=12, ge=1, le=25)
    jurisdiction_filter: Optional[str] = None
    status_filter: Optional[str] = None
    include_cross_jurisdiction: bool = True
    include_failed: bool = True
    include_enacted: bool = True
    include_in_progress: bool = True


class SearchMetrics(BaseModel):
    extracted_seconds: float = 0.0
    profile_seconds: float = 0.0
    lexical_seconds: float = 0.0
    semantic_seconds: float = 0.0
    llm_rerank_seconds: float = 0.0


class ErrorResponse(BaseModel):
    detail: str
    context: Optional[dict[str, Any]] = None


WorkflowStage = Literal["upload", "metadata", "similarity", "step3", "step4", "step5", "done"]
WorkflowStatus = Literal["waiting_user", "running", "waiting_approval", "completed", "error"]
WorkflowEventKind = Literal["system", "metadata", "search", "user", "agent", "diff", "approval", "command", "web", "error"]
WorkflowApprovalDecision = Literal["accept", "decline", "cancel"]
MetadataStatus = Literal["not_started", "generating", "ready", "confirmed"]
SimilarityStatus = Literal["not_started", "running", "ready", "error"]


class WorkflowSourceSection(BaseModel):
    label: str = ""
    heading: str = ""
    text: str = ""


class WorkflowSourceBill(BaseModel):
    bill_id: str
    identifier: str
    title: str
    jurisdiction_name: str
    session_identifier: str = ""
    derived_status: str = ""
    primary_bill_url: Optional[str] = None
    match_reason: str = ""
    summary: str = ""
    excerpt: str = ""
    full_text: str = ""
    sections: List[WorkflowSourceSection] = Field(default_factory=list)


class WorkflowPendingApproval(BaseModel):
    request_id: str
    item_id: str
    turn_id: str
    diff: str = ""
    reason: str = ""
    file_paths: List[str] = Field(default_factory=list)
    created_at: str
    decision: str = ""
    resolved_at: str = ""


class WorkflowEvent(BaseModel):
    event_id: str
    kind: WorkflowEventKind
    title: str = ""
    body: str = ""
    phase: str = ""
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class WorkflowSteerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class WorkflowMetadataUpdateRequest(BaseModel):
    profile: UploadedBillProfile


class StakeholderEvidenceSource(BaseModel):
    title: str = ""
    organization: str = ""
    url: str = ""
    published_at: str = ""
    source_type: str = ""
    relevance: str = ""
    summary: str = ""


class StakeholderActor(BaseModel):
    name: str = ""
    category: str = ""
    likely_position: str = ""
    lobbying_power: str = ""
    affected_entities_estimate: str = ""
    sme_exposure: str = ""
    key_concerns: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    costs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)


class StakeholderImprovement(BaseModel):
    title: str = ""
    objective: str = ""
    stakeholder_problem: str = ""
    legislative_strategy: str = ""
    targeted_text: str = ""
    reason: str = ""
    stakeholder_groups: List[str] = Field(default_factory=list)
    expected_effect: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    status: Literal["planned", "proposed", "applied", "skipped"] = "planned"


class StakeholderReport(BaseModel):
    status: Literal["not_started", "in_progress", "ready"] = "not_started"
    summary: str = ""
    estimated_affected_entities: str = ""
    sme_impact_test: str = ""
    distributional_impacts: str = ""
    implementation_feasibility: str = ""
    beneficiaries_vs_cost_bearers: str = ""
    political_viability: str = ""
    optimization_focus: List[str] = Field(default_factory=list)
    actors: List[StakeholderActor] = Field(default_factory=list)
    sources: List[StakeholderEvidenceSource] = Field(default_factory=list)
    proposed_improvements: List[StakeholderImprovement] = Field(default_factory=list)


class WorkflowSession(BaseModel):
    session_id: str
    original_filename: str
    file_type: str
    created_at: str
    updated_at: str
    status: WorkflowStatus = "waiting_user"
    current_stage: WorkflowStage = "upload"
    thread_id: str = ""
    active_turn_id: str = ""
    workspace_dir: str = ""
    current_draft_text: str
    current_draft_version: int = 1
    profile: UploadedBillProfile = Field(default_factory=UploadedBillProfile)
    metadata_status: MetadataStatus = "not_started"
    metadata_last_generated_at: str = ""
    results: List[CandidateBill] = Field(default_factory=list)
    similarity_status: SimilarityStatus = "not_started"
    similarity_progress_message: str = ""
    similarity_last_completed_at: str = ""
    search_timings: dict[str, float] = Field(default_factory=dict)
    source_bills: List[WorkflowSourceBill] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    events: List[WorkflowEvent] = Field(default_factory=list)
    pending_approval: WorkflowPendingApproval | None = None
    stakeholder_report: StakeholderReport = Field(default_factory=StakeholderReport)
    latest_agent_message: str = ""
    final_message: str = ""
    current_diff: str = ""
    error_message: str = ""
    completion_summary: str = ""
