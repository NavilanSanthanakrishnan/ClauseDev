from fastapi import APIRouter

from app.core.config import (
    SUPABASE_AUTH_APPROVAL_REQUIRED,
    SUPABASE_URL,
)

router = APIRouter()

@router.get("/status")
async def auth_status():
    return {
        "mode": "supabase",
        "enabled": bool(SUPABASE_URL),
        "approval_required": SUPABASE_AUTH_APPROVAL_REQUIRED,
    }