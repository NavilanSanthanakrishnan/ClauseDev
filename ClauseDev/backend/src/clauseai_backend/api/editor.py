from fastapi import APIRouter, Depends, HTTPException, status

from clauseai_backend.api.deps import get_current_user, get_editor_runtime
from clauseai_backend.models.auth import User
from clauseai_backend.schemas.editor import EditorSessionEventResponse, EditorSessionResponse, EditorSteerRequest
from clauseai_backend.services.editor_runtime import EditorRuntimeManager

router = APIRouter(prefix="/api/projects", tags=["editor-runtime"])


@router.post("/{project_id}/editor/session", response_model=EditorSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_editor_session(
    project_id: str,
    runtime: EditorRuntimeManager = Depends(get_editor_runtime),
    current_user: User = Depends(get_current_user),
) -> EditorSessionResponse:
    try:
        session = await runtime.start_or_resume(project_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return EditorSessionResponse.model_validate(session)


@router.get("/{project_id}/editor/session", response_model=EditorSessionResponse | None)
async def get_editor_session(
    project_id: str,
    runtime: EditorRuntimeManager = Depends(get_editor_runtime),
    current_user: User = Depends(get_current_user),
) -> EditorSessionResponse | None:
    try:
        session = runtime.find_session(project_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if not session:
        return None
    return EditorSessionResponse.model_validate(session)


@router.get("/{project_id}/editor/session/events", response_model=list[EditorSessionEventResponse])
async def list_editor_session_events(
    project_id: str,
    runtime: EditorRuntimeManager = Depends(get_editor_runtime),
    current_user: User = Depends(get_current_user),
) -> list[EditorSessionEventResponse]:
    try:
        events = runtime.list_events(project_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [EditorSessionEventResponse.model_validate(item) for item in events]


@router.post("/{project_id}/editor/session/steer", response_model=EditorSessionResponse)
async def steer_editor_session(
    project_id: str,
    payload: EditorSteerRequest,
    runtime: EditorRuntimeManager = Depends(get_editor_runtime),
    current_user: User = Depends(get_current_user),
) -> EditorSessionResponse:
    try:
        session = await runtime.steer(project_id, current_user.user_id, payload.message)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return EditorSessionResponse.model_validate(session)


@router.post("/{project_id}/editor/session/approve", response_model=EditorSessionResponse)
async def approve_editor_diff(
    project_id: str,
    runtime: EditorRuntimeManager = Depends(get_editor_runtime),
    current_user: User = Depends(get_current_user),
) -> EditorSessionResponse:
    try:
        session = await runtime.approve(project_id, current_user.user_id, "accept")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return EditorSessionResponse.model_validate(session)


@router.post("/{project_id}/editor/session/reject", response_model=EditorSessionResponse)
async def reject_editor_diff(
    project_id: str,
    runtime: EditorRuntimeManager = Depends(get_editor_runtime),
    current_user: User = Depends(get_current_user),
) -> EditorSessionResponse:
    try:
        session = await runtime.approve(project_id, current_user.user_id, "decline")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return EditorSessionResponse.model_validate(session)
