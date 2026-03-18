from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.supabase_auth import AuthenticatedUser
from app.services.supabase_service import (
    archive_workflow_history,
    delete_workflow_history,
    get_user_workflow,
    get_workflow_history_entry,
    list_workflow_history,
    upsert_user_workflow,
)

router = APIRouter()

class WorkflowUpsertRequest(BaseModel):
    workflow: Dict[str, Any] = Field(default_factory=dict)
    current_step: Optional[str] = None

class ArchiveWorkflowRequest(BaseModel):
    title: str = "Untitled Workflow"
    reason: str = "manual"
    current_step: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    snapshot: Dict[str, Any] = Field(default_factory=dict)

class RestoreWorkflowRequest(BaseModel):
    history_id: str

@router.get("/current")
async def get_current_workflow(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    row = get_user_workflow(current_user.user_id)
    if not row:
        row = upsert_user_workflow(current_user.user_id, {}, current_step="/")
    return {
        "workflow": row.get("workflow_json") or {},
        "current_step": row.get("current_step"),
        "updated_at": row.get("updated_at"),
    }

@router.put("/current")
async def put_current_workflow(
    body: WorkflowUpsertRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    row = upsert_user_workflow(current_user.user_id, body.workflow, current_step=body.current_step)
    return {
        "workflow": row.get("workflow_json") or {},
        "current_step": row.get("current_step"),
        "updated_at": row.get("updated_at"),
    }

@router.get("/history")
async def get_workflow_history(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, List[Dict[str, Any]]]:
    rows = list_workflow_history(current_user.user_id, limit=30)
    return {"items": rows}

@router.post("/history/archive")
async def archive_workflow(
    body: ArchiveWorkflowRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    snapshot = body.snapshot or {}
    if not snapshot:
        current = get_user_workflow(current_user.user_id)
        snapshot = (current or {}).get("workflow_json") or {}

    record = archive_workflow_history(
        user_id=current_user.user_id,
        title=body.title,
        reason=body.reason,
        current_step=body.current_step,
        summary=body.summary,
        snapshot=snapshot,
    )
    return {
        "item": record,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }

@router.post("/history/restore")
async def restore_workflow(
    body: RestoreWorkflowRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    entry = get_workflow_history_entry(current_user.user_id, body.history_id)
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")

    snapshot = entry.get("snapshot") or {}
    current_step = entry.get("current_step") or snapshot.get("currentStep") or "/"
    row = upsert_user_workflow(current_user.user_id, snapshot, current_step=current_step)
    return {
        "workflow": row.get("workflow_json") or {},
        "current_step": row.get("current_step"),
        "updated_at": row.get("updated_at"),
        "history_id": body.history_id,
    }

@router.delete("/history/{history_id}")
async def remove_workflow_history(
    history_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    delete_workflow_history(current_user.user_id, history_id)
    return {"success": True, "history_id": history_id}