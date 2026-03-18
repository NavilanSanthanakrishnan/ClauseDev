from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from clauseai_backend.db.session import ReferenceDatabases
from clauseai_backend.models.projects import (
    AnalysisArtifact,
    BillDraft,
    Project,
    ProjectMetadata,
    Suggestion,
)
from clauseai_backend.models.workflow import PipelineRun, PipelineStep
from clauseai_backend.services.analysis import (
    AnalysisResult,
    build_legal_analysis,
    build_similar_bills_analysis,
    build_stakeholder_analysis,
)
from clauseai_backend.services.drafting_agent import build_editor_agent_pass
from clauseai_backend.services.metadata import generate_metadata_from_text

STAGE_STEP_MAP: dict[str, list[str]] = {
    "upload": ["store-source", "extract-text"],
    "metadata": ["generate-metadata", "review-metadata"],
    "similar-bills": ["profile-bill", "search-candidates", "rerank-candidates", "write-report"],
    "legal": ["retrieve-laws", "classify-conflicts", "write-report"],
    "stakeholders": ["retrieve-context", "analyze-opposition", "write-report"],
    "editor": ["load-context", "prepare-suggestions"],
}


def create_pipeline_run(db: Session, project: Project, requested_by: str, stage_name: str) -> PipelineRun:
    run = PipelineRun(
        run_id=str(uuid4()),
        project_id=project.project_id,
        stage_name=stage_name,
        requested_by=requested_by,
        status="queued",
    )
    db.add(run)
    steps = STAGE_STEP_MAP.get(stage_name, ["start", "complete"])
    for step_name in steps:
        db.add(
            PipelineStep(
                step_id=str(uuid4()),
                run_id=run.run_id,
                step_name=step_name,
                status="pending",
            )
        )
    project.current_stage = stage_name
    db.add(project)
    db.commit()
    db.refresh(run)
    return run


def execute_pipeline_run(db: Session, run: PipelineRun, reference_db: ReferenceDatabases) -> PipelineRun:
    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()

    step_rows = (
        db.execute(select(PipelineStep).where(PipelineStep.run_id == run.run_id).order_by(PipelineStep.created_at.asc()))
        .scalars()
        .all()
    )
    try:
        project = db.get(Project, run.project_id)
        if not project:
            raise RuntimeError("Project missing for pipeline run")

        for step in step_rows:
            step.status = "running"
            step.started_at = datetime.now(timezone.utc)
            db.add(step)
        db.commit()

        output = _execute_stage(db, reference_db, project, run.stage_name)
        for step in step_rows:
            step.status = "completed"
            step.output_json = output
            step.finished_at = datetime.now(timezone.utc)
            db.add(step)
        db.commit()

        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
    except Exception as exc:
        failed_step = next((item for item in step_rows if item.status == "running"), None)
        if failed_step:
            failed_step.status = "failed"
            failed_step.error_json = {"message": str(exc)}
            failed_step.finished_at = datetime.now(timezone.utc)
            db.add(failed_step)
        run.status = "failed"
        run.error_summary = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.add(run)
        db.commit()
    db.refresh(run)
    return run


def _execute_stage(db: Session, reference_db: ReferenceDatabases, project: Project, stage_name: str) -> dict[str, object]:
    if stage_name == "upload":
        return {"status": "noop", "message": "Upload stage is handled during file submission."}

    draft = db.scalar(select(BillDraft).where(BillDraft.project_id == project.project_id))
    if not draft:
        raise RuntimeError("Draft missing for project")

    if stage_name == "metadata":
        if not draft.current_text.strip():
            raise RuntimeError("Draft text is required before metadata generation.")
        payload = generate_metadata_from_text(draft.current_text, project.title)
        metadata = db.get(ProjectMetadata, project.project_id)
        if not metadata:
            metadata = ProjectMetadata(
                project_id=project.project_id,
                title=str(payload["title"]),
                description=str(payload["description"]),
                summary=str(payload["summary"]),
                keywords=list(payload["keywords"]),
                generated_json=payload,
            )
        else:
            metadata.title = str(payload["title"])
            metadata.description = str(payload["description"])
            metadata.summary = str(payload["summary"])
            metadata.keywords = list(payload["keywords"])
            metadata.generated_json = payload
        project.current_stage = "metadata"
        db.add(metadata)
        db.add(project)
        db.commit()
        return payload

    metadata = db.get(ProjectMetadata, project.project_id)
    if not metadata:
        raise RuntimeError("Metadata must be generated before this stage.")

    if stage_name == "similar-bills":
        result = build_similar_bills_analysis(
            reference_db,
            title=metadata.title,
            summary=metadata.summary,
            keywords=list(metadata.keywords),
            draft_text=draft.current_text,
        )
    elif stage_name == "legal":
        result = build_legal_analysis(
            reference_db,
            title=metadata.title,
            summary=metadata.summary,
            keywords=list(metadata.keywords),
            draft_text=draft.current_text,
        )
    elif stage_name == "stakeholders":
        result = build_stakeholder_analysis(
            title=metadata.title,
            summary=metadata.summary,
            keywords=list(metadata.keywords),
            draft_text=draft.current_text,
        )
    elif stage_name == "editor":
        pending_suggestions = (
            db.execute(
                select(Suggestion)
                .where(Suggestion.project_id == project.project_id, Suggestion.status == "pending")
                .order_by(Suggestion.created_at.asc())
            )
            .scalars()
            .all()
        )
        payload = build_editor_agent_pass(
            draft_text=draft.current_text,
            project_title=project.title,
            metadata=metadata.generated_json,
            suggestions=[
                {
                    "stage_name": item.stage_name,
                    "title": item.title,
                    "rationale": item.rationale,
                    "before_text": item.before_text,
                    "after_text": item.after_text,
                    "source_refs": list(item.source_refs),
                }
                for item in pending_suggestions
            ],
        )
        if not payload:
            raise RuntimeError("Codex runtime is not available for editor stage.")
        result = AnalysisResult(
            markdown=str(payload.get("report") or "No report generated."),
            payload=payload,
            suggestions=[
                {
                    "title": str(item.get("title") or "Untitled suggestion"),
                    "rationale": str(item.get("rationale") or ""),
                    "before_text": str(item.get("before_text") or ""),
                    "after_text": str(item.get("after_text") or ""),
                    "source_refs": list(item.get("source_refs") or []),
                }
                for item in (payload.get("suggestions") or [])
                if isinstance(item, dict)
            ],
        )
    else:
        raise RuntimeError(f"Unknown stage {stage_name}")

    _replace_stage_outputs(db, project.project_id, stage_name, result)
    project.current_stage = stage_name
    project.status = "in_review" if stage_name == "editor" else "analysis_ready"
    db.add(project)
    db.commit()
    return result.payload


def _replace_stage_outputs(db: Session, project_id: str, stage_name: str, result: AnalysisResult) -> None:
    db.execute(delete(Suggestion).where(Suggestion.project_id == project_id, Suggestion.stage_name == stage_name))
    db.execute(delete(AnalysisArtifact).where(AnalysisArtifact.project_id == project_id, AnalysisArtifact.stage_name == stage_name))
    artifact = AnalysisArtifact(
        artifact_id=str(uuid4()),
        project_id=project_id,
        stage_name=stage_name,
        artifact_kind="report",
        status="ready",
        markdown_content=result.markdown,
        payload_json=result.payload,
    )
    db.add(artifact)
    for item in result.suggestions:
        db.add(
            Suggestion(
                suggestion_id=str(uuid4()),
                project_id=project_id,
                stage_name=stage_name,
                title=str(item["title"]),
                rationale=str(item["rationale"]),
                before_text=str(item.get("before_text") or ""),
                after_text=str(item.get("after_text") or ""),
                source_refs=list(item.get("source_refs") or []),
            )
        )
    db.flush()
