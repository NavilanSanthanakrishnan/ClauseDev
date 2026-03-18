import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, Optional
import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError, PyJWKClient

from app.core.config import (
    SUPABASE_AUTH_APPROVAL_REQUIRED,
    SUPABASE_JWKS_URL,
    SUPABASE_JWT_SECRET,
)
from app.services.supabase_service import SupabaseNotConfiguredError, ensure_user_profile

logger = logging.getLogger(__name__)

@dataclass
class AuthenticatedUser:
    user_id: str
    email: Optional[str]
    claims: Dict[str, Any]
    profile: Dict[str, Any]

@lru_cache(maxsize=1)
def _get_jwks_client() -> Optional[PyJWKClient]:
    if not SUPABASE_JWKS_URL:
        return None
    return PyJWKClient(SUPABASE_JWKS_URL)

def _decode_token(token: str) -> Dict[str, Any]:
    unverified_header = jwt.get_unverified_header(token)
    algorithm = str(unverified_header.get("alg") or "").upper()

    if algorithm.startswith("HS") and SUPABASE_JWT_SECRET:
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256", "HS384", "HS512"],
            options={"verify_aud": False, "verify_iss": False},
        )

    jwks_client = _get_jwks_client()
    if not jwks_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase JWT verification is not configured",
        )

    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256", "EdDSA"],
        options={"verify_aud": False, "verify_iss": False},
    )

def _extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("Authorization", "")
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    return parts[1].strip()

def authenticate_request(request: Request) -> AuthenticatedUser:
    token = _extract_bearer_token(request)
    try:
        claims = _decode_token(token)
    except InvalidTokenError as error:
        logger.warning("JWT verification failed", extra={"event": "auth_jwt_invalid", "error": str(error)})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth token") from error

    user_id = str(claims.get("sub") or "").strip()
    email = claims.get("email")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth token missing subject")

    try:
        profile = ensure_user_profile(user_id=user_id, email=email)
    except SupabaseNotConfiguredError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - external dependency
        logger.exception("Failed ensuring user profile", extra={"event": "auth_profile_ensure_failed", "user_id": user_id})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load user profile") from error

    if SUPABASE_AUTH_APPROVAL_REQUIRED and not bool(profile.get("approved")):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is pending approval")

    return AuthenticatedUser(user_id=user_id, email=email, claims=claims, profile=profile)
