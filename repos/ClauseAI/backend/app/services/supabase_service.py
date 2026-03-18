import logging
from functools import lru_cache
from typing import Any, Dict, List, Optional
from supabase import Client, create_client

from app.core.config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL

logger = logging.getLogger(__name__)

class SupabaseNotConfiguredError(RuntimeError):
    pass

def _validate_config() -> None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise SupabaseNotConfiguredError(
            "Supabase admin client is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
        )

@lru_cache(maxsize=1)
def get_admin_client() -> Client:
    _validate_config()
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_admin_client()
    response = client.table("app_users").select("*").eq("user_id", user_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None

def ensure_user_profile(user_id: str, email: Optional[str]) -> Dict[str, Any]:
    existing = get_user_profile(user_id)
    if existing:
        if email and existing.get("email") != email:
            return update_user_profile(user_id, {"email": email})
        return existing

    payload = {
        "user_id": user_id,
        "email": email,
        "display_name": email,
    }
    client = get_admin_client()
    response = client.table("app_users").insert(payload).execute()
    rows = response.data or []
    if rows:
        return rows[0]
    return get_user_profile(user_id) or payload

def update_user_profile(user_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    client = get_admin_client()
    response = (
        client.table("app_users")
        .update(patch)
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    if rows:
        return rows[0]
    profile = ensure_user_profile(user_id, patch.get("email"))
    if patch:
        result = (
            client.table("app_users")
            .update(patch)
            .eq("user_id", user_id)
            .execute()
        )
        updated_rows = result.data or []
        if updated_rows:
            profile = updated_rows[0]
    return profile

def get_user_workflow(user_id: str) -> Optional[Dict[str, Any]]:
    client = get_admin_client()
    response = client.table("user_workflows").select("*").eq("user_id", user_id).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None

def upsert_user_workflow(user_id: str, workflow_json: Dict[str, Any], current_step: Optional[str]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "user_id": user_id,
        "workflow_json": workflow_json,
    }
    if current_step is not None:
        payload["current_step"] = current_step

    client = get_admin_client()
    response = client.table("user_workflows").upsert(payload, on_conflict="user_id").execute()
    rows = response.data or []
    if rows:
        return rows[0]
    return get_user_workflow(user_id) or payload

def list_workflow_history(user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    client = get_admin_client()
    response = (
        client.table("workflow_history")
        .select("*")
        .eq("user_id", user_id)
        .order("saved_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []

def archive_workflow_history(
    user_id: str,
    title: str,
    reason: str,
    current_step: Optional[str],
    summary: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    payload = {
        "user_id": user_id,
        "title": title,
        "reason": reason,
        "current_step": current_step,
        "summary": summary,
        "snapshot": snapshot,
    }
    client = get_admin_client()
    response = client.table("workflow_history").insert(payload).execute()
    rows = response.data or []
    return rows[0] if rows else payload

def get_workflow_history_entry(user_id: str, entry_id: str) -> Optional[Dict[str, Any]]:
    client = get_admin_client()
    response = (
        client.table("workflow_history")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", entry_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None

def delete_workflow_history(user_id: str, entry_id: str) -> None:
    client = get_admin_client()
    client.table("workflow_history").delete().eq("user_id", user_id).eq("id", entry_id).execute()

def record_user_file(
    user_id: str,
    bucket: str,
    path: str,
    original_name: Optional[str],
    mime_type: Optional[str],
    size_bytes: Optional[int],
) -> Dict[str, Any]:
    payload = {
        "user_id": user_id,
        "bucket": bucket,
        "path": path,
        "original_name": original_name,
        "mime_type": mime_type,
        "size_bytes": size_bytes,
    }
    client = get_admin_client()
    response = client.table("user_files").insert(payload).execute()
    rows = response.data or []
    return rows[0] if rows else payload

def download_storage_bytes(bucket: str, path: str) -> bytes:
    client = get_admin_client()
    return client.storage.from_(bucket).download(path)

def upload_storage_bytes(
    bucket: str,
    path: str,
    content: bytes,
    content_type: Optional[str] = None,
    upsert: bool = False,
) -> Any:
    client = get_admin_client()
    options: Dict[str, Any] = {"upsert": str(bool(upsert)).lower()}
    if content_type:
        options["content-type"] = content_type
    return client.storage.from_(bucket).upload(path, content, options)

def list_storage_objects(bucket: str, prefix: str = "") -> List[Dict[str, Any]]:
    client = get_admin_client()
    return client.storage.from_(bucket).list(prefix or None) or []