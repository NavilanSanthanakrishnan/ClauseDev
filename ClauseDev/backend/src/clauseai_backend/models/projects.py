from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from clauseai_backend.db.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = {"schema": "app"}

    project_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("auth.users.user_id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    jurisdiction_type: Mapped[str] = mapped_column(String(64))
    jurisdiction_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(64), default="draft")
    current_stage: Mapped[str] = mapped_column(String(64), default="upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BillDraft(Base):
    __tablename__ = "bill_drafts"
    __table_args__ = {"schema": "app"}

    draft_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    current_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class BillDraftVersion(Base):
    __tablename__ = "bill_draft_versions"
    __table_args__ = {"schema": "app"}

    version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    draft_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("app.bill_drafts.draft_id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int]
    source_kind: Mapped[str] = mapped_column(String(64), default="manual")
    content_text: Mapped[str] = mapped_column(Text, default="")
    change_summary: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SourceDocument(Base):
    __tablename__ = "source_documents"
    __table_args__ = {"schema": "app"}

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    storage_path: Mapped[str] = mapped_column(String(500))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ProjectMetadata(Base):
    __tablename__ = "project_metadata"
    __table_args__ = {"schema": "app"}

    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    generated_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class AnalysisArtifact(Base):
    __tablename__ = "analysis_artifacts"
    __table_args__ = {"schema": "app"}

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True)
    stage_name: Mapped[str] = mapped_column(String(64), index=True)
    artifact_kind: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="ready")
    markdown_content: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class Suggestion(Base):
    __tablename__ = "suggestions"
    __table_args__ = {"schema": "app"}

    suggestion_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("app.projects.project_id", ondelete="CASCADE"), index=True)
    stage_name: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    rationale: Mapped[str] = mapped_column(Text, default="")
    before_text: Mapped[str] = mapped_column(Text, default="")
    after_text: Mapped[str] = mapped_column(Text, default="")
    source_refs: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
