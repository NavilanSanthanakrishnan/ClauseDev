from fastapi import HTTPException, Request, status

from app.core.supabase_auth import AuthenticatedUser

def get_current_user(request: Request) -> AuthenticatedUser:
    current = getattr(request.state, "current_user", None)
    if current is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return current