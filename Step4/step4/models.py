from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class BillClause(BaseModel):
    label: str = ""
    effect: str = ""
    text: str = ""


class UploadedBillProfile(BaseModel):
    title: str = ""
    summary: str = ""
    origin_country: str = ""
    origin_country_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    origin_state_code: str = ""
    origin_state_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bill_category: str = ""
    policy_domains: List[str] = Field(default_factory=list)
    affected_entities: List[str] = Field(default_factory=list)
    required_actions: List[str] = Field(default_factory=list)
    prohibited_actions: List[str] = Field(default_factory=list)
    permissions_created: List[str] = Field(default_factory=list)
    enforcement_mechanisms: List[str] = Field(default_factory=list)
    named_agencies: List[str] = Field(default_factory=list)
    explicit_citations: List[str] = Field(default_factory=list)
    conflict_search_phrases: List[str] = Field(default_factory=list)
    key_clauses: List[BillClause] = Field(default_factory=list)


class LegalCandidate(BaseModel):
    document_id: str
    source_system: str
    source_kind: str
    citation: str
    heading: str = ""
    hierarchy_path: str = ""
    source_url: Optional[str] = None
    body_text: str = ""
    excerpt: str = ""
    matched_queries: List[str] = Field(default_factory=list)
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    final_score: float = 0.0


class ConflictFinding(BaseModel):
    candidate_id: str
    source_system: str
    source_kind: str
    citation: str
    heading: str = ""
    hierarchy_path: str = ""
    source_url: Optional[str] = None
    conflict_type: str
    severity: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bill_excerpt: str
    statute_excerpt: str
    explanation: str
    why_conflict: str = ""


class ConflictJudgeItem(BaseModel):
    candidate_id: str
    conflict_type: str
    severity: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bill_excerpt: str = ""
    statute_excerpt: str = ""
    explanation: str = ""
    why_conflict: str = ""


class ConflictJudgeResponse(BaseModel):
    conflicts: List[ConflictJudgeItem] = Field(default_factory=list)
    notes: str = ""


class CandidateVerificationResponse(BaseModel):
    is_conflict: bool = False
    conflict_type: str = ""
    severity: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    bill_excerpt: str = ""
    statute_excerpt: str = ""
    explanation: str = ""
    why_conflict: str = ""


class ConflictSearchResult(BaseModel):
    filename: str
    file_type: str
    extracted_text_preview: str
    extracted_text_length: int
    profile: UploadedBillProfile
    conflicts: List[ConflictFinding]
    candidate_counts: dict[str, int]
    timings: dict[str, float]
    warnings: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    databases_ready: bool
    missing_indexes: dict[str, list[str]] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    detail: str
    context: Optional[dict[str, Any]] = None
