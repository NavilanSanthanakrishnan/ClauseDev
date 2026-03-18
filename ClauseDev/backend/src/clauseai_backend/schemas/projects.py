from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    jurisdiction_type: str = Field(min_length=2, max_length=64)
    jurisdiction_name: str = Field(min_length=2, max_length=255)
    initial_text: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    title: str
    jurisdiction_type: str
    jurisdiction_name: str
    status: str
    current_stage: str
    created_at: datetime
    updated_at: datetime


class MetadataResponse(BaseModel):
    title: str
    description: str
    summary: str
    keywords: list[str]
    extras: dict[str, object] = Field(default_factory=dict)


class MetadataUpdateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(default="", max_length=5000)
    summary: str = Field(default="", max_length=12000)
    keywords: list[str] = Field(default_factory=list)
    extras: dict[str, object] = Field(default_factory=dict)


class ArtifactResponse(BaseModel):
    artifact_id: str
    stage_name: str
    artifact_kind: str
    status: str
    markdown_content: str
    payload_json: dict[str, object]


class DraftResponse(BaseModel):
    draft_id: str
    title: str
    current_text: str


class DraftVersionResponse(BaseModel):
    version_id: str
    version_number: int
    source_kind: str
    content_text: str
    change_summary: dict[str, object]
    created_at: datetime


class DraftSaveRequest(BaseModel):
    content_text: str = Field(min_length=1)
    change_reason: str = Field(min_length=3, max_length=255)


class SuggestionActionRequest(BaseModel):
    after_text: str | None = None
    change_reason: str = Field(default="Applied suggestion", min_length=3, max_length=255)


class AgentPassResponse(BaseModel):
    artifact_id: str
    markdown_content: str
    payload_json: dict[str, object]
    suggestion_count: int


class SuggestionResponse(BaseModel):
    suggestion_id: str
    stage_name: str
    title: str
    rationale: str
    before_text: str
    after_text: str
    source_refs: list[dict[str, object]]
    status: str
