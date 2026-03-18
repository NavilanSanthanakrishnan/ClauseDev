import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.supabase_auth import AuthenticatedUser
from app.services.supabase_service import update_user_profile

router = APIRouter()
logger = logging.getLogger(__name__)

class UserProfilePatch(BaseModel):
    username: Optional[str] = None
    display_name: Optional[str] = None

@router.get("/me")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> Dict[str, Any]:
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "profile": current_user.profile,
        "approved": bool(current_user.profile.get("approved")),
    }

@router.patch("/me")
async def patch_me(
    patch: UserProfilePatch,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if patch.username is not None:
        updates["username"] = patch.username.strip() or None
    if patch.display_name is not None:
        updates["display_name"] = patch.display_name.strip() or None

    if not updates:
        return {
            "user_id": current_user.user_id,
            "email": current_user.email,
            "profile": current_user.profile,
            "approved": bool(current_user.profile.get("approved")),
        }

    profile = update_user_profile(current_user.user_id, updates)
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "profile": profile,
        "approved": bool(profile.get("approved")),
    }