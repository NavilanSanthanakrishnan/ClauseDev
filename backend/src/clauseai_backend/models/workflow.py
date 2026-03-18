from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clauseai_backend.db.base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = {"schema": "workflow"}

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True)
    stage_name: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    attempt_count: Mapped[int] = mapped_column(default=1)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("auth.users.user_id", ondelete="SET NULL"))
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PipelineStep(Base):
    __tablename__ = "pipeline_steps"
    __table_args__ = {"schema": "workflow"}

    step_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workflow.pipeline_runs.run_id", ondelete="CASCADE"), index=True
    )
    step_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    worker_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    error_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
