from __future__ import annotations

from typing import Any, List, Optional

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

