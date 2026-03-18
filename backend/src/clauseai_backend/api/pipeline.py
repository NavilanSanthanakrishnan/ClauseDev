from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseai_backend.api.deps import get_current_user, get_reference_db, get_user_db
from clauseai_backend.models.auth import User
from clauseai_backend.models.projects import Project
from clauseai_backend.schemas.workflow import PipelineRunCreate, PipelineRunResponse
from clauseai_backend.workflows.orchestrator import create_pipeline_run, execute_pipeline_run
from clauseai_backend.models.workflow import PipelineRun

router = APIRouter(prefix="/api/projects", tags=["pipeline"])


@router.post("/{project_id}/pipeline-runs", response_model=PipelineRunResponse, status_code=status.HTTP_201_CREATED)
def start_pipeline_run(
    project_id: str,
    payload: PipelineRunCreate,
    db: Session = Depends(get_user_db),
    reference_db: Session = Depends(get_reference_db),
    current_user: User = Depends(get_current_user),
) -> PipelineRunResponse:
    project = db.scalar(
        select(Project).where(Project.project_id == project_id, Project.user_id == current_user.user_id)
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    run = create_pipeline_run(db=db, project=project, requested_by=current_user.user_id, stage_name=payload.stage_name)
    run = execute_pipeline_run(db=db, run=run, reference_db=reference_db)
    return PipelineRunResponse.model_validate(run)


@router.get("/{project_id}/pipeline-runs", response_model=list[PipelineRunResponse])
def list_pipeline_runs(
    project_id: str,
    db: Session = Depends(get_user_db),
    current_user: User = Depends(get_current_user),
) -> list[PipelineRunResponse]:
    project = db.scalar(
        select(Project).where(Project.project_id == project_id, Project.user_id == current_user.user_id)
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    runs = (
        db.execute(
            select(PipelineRun)
            .where(PipelineRun.project_id == project.project_id)
            .order_by(PipelineRun.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [PipelineRunResponse.model_validate(run) for run in runs]
