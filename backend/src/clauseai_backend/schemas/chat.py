from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatThreadCreate(BaseModel):
    project_id: str | None = None
    title: str = Field(default="Research thread", min_length=3, max_length=255)


class ChatThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    project_id: str | None
    title: str
    scope: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=3)


class ChatMessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    citations: list[dict[str, object]]
    created_at: datetime
