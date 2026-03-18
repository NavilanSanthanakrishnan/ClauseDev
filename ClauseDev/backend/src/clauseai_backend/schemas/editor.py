from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EditorApprovalResponse(BaseModel):
    request_id: str
    item_id: str
    turn_id: str
    diff: str = ""
    reason: str = ""
    file_paths: list[str] = Field(default_factory=list)
    created_at: str


class EditorSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    project_id: str
    thread_id: str
    active_turn_id: str
    status: str
    current_stage: str
    workspace_dir: str
    latest_agent_message: str
    final_message: str
    current_diff: str
    completion_summary: str
    error_message: str
    pending_approval: dict[str, object]
    created_at: datetime
    updated_at: datetime


class EditorSessionEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    session_id: str
    project_id: str
    kind: str
    title: str
    body: str
    phase: str
    metadata_json: dict[str, object]
    created_at: datetime


class EditorSteerRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
