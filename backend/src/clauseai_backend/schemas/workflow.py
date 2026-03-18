from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PipelineRunCreate(BaseModel):
    stage_name: str = Field(min_length=3, max_length=64)


class PipelineRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    project_id: str
    stage_name: str
    status: str
    attempt_count: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_summary: str | None
