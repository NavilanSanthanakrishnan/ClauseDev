from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clauseai_backend.db.base import Base


class EditorSession(Base):
    __tablename__ = "editor_sessions"
    __table_args__ = {"schema": "app"}

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True, unique=True
    )
    thread_id: Mapped[str] = mapped_column(String(255), default="")
    active_turn_id: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="idle")
    current_stage: Mapped[str] = mapped_column(String(64), default="similar-bills")
    workspace_dir: Mapped[str] = mapped_column(String(500), default="")
    latest_agent_message: Mapped[str] = mapped_column(Text, default="")
    final_message: Mapped[str] = mapped_column(Text, default="")
    current_diff: Mapped[str] = mapped_column(Text, default="")
    completion_summary: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    pending_approval: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class EditorSessionEvent(Base):
    __tablename__ = "editor_session_events"
    __table_args__ = {"schema": "app"}

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("app.editor_sessions.session_id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), default="system")
    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    phase: Mapped[str] = mapped_column(String(64), default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
