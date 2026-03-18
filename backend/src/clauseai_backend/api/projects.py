from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseai_backend.api.deps import get_current_user, get_user_db
from clauseai_backend.models.auth import User
from clauseai_backend.models.projects import BillDraft, BillDraftVersion, Project
from clauseai_backend.schemas.projects import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_user_db), current_user: User = Depends(get_current_user)
) -> list[ProjectResponse]:
    projects = (
        db.execute(select(Project).where(Project.user_id == current_user.user_id).order_by(Project.updated_at.desc()))
        .scalars()
        .all()
    )
    return [ProjectResponse.model_validate(project) for project in projects]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_user_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = Project(
        project_id=str(uuid4()),
        user_id=current_user.user_id,
        title=payload.title,
        jurisdiction_type=payload.jurisdiction_type,
        jurisdiction_name=payload.jurisdiction_name,
    )
    db.add(project)
    db.flush()
    draft = BillDraft(
        draft_id=str(uuid4()),
        project_id=project.project_id,
        title=payload.title,
        current_text=payload.initial_text or "",
    )
    version = BillDraftVersion(
        version_id=str(uuid4()),
        draft_id=draft.draft_id,
        project_id=project.project_id,
        version_number=1,
        source_kind="initial",
        content_text=payload.initial_text or "",
        change_summary={"reason": "Project created"},
        created_by=current_user.user_id,
    )
    db.add(draft)
    db.add(version)
    db.commit()
    db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_user_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = db.scalar(
        select(Project).where(Project.project_id == project_id, Project.user_id == current_user.user_id)
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)
