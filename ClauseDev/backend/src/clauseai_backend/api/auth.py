from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseai_backend.api.deps import get_current_user, get_user_db
from clauseai_backend.core.security import (
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from clauseai_backend.models.auth import RefreshToken, User
from clauseai_backend.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_auth_tokens(db: Session, user: User) -> AuthResponse:
    plain_refresh_token = generate_refresh_token()
    refresh_record = RefreshToken(
        token_id=str(uuid4()),
        user_id=user.user_id,
        token_hash=hash_refresh_token(plain_refresh_token),
    )
    db.add(refresh_record)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    access_token = create_access_token(subject=user.user_id, email=user.email)
    return AuthResponse(
        access_token=access_token,
        refresh_token=plain_refresh_token,
        user=UserResponse.model_validate(user),
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_user_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    existing = db.scalar(select(User).where(User.email == normalized_email))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in use")

    user = User(
        user_id=str(uuid4()),
        email=normalized_email,
        password_hash=get_password_hash(payload.password),
        display_name=payload.display_name.strip() if payload.display_name else normalized_email,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _issue_auth_tokens(db, user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_user_db)) -> AuthResponse:
    normalized_email = payload.email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    return _issue_auth_tokens(db, user)


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_user_db)) -> AuthResponse:
    token_hash = hash_refresh_token(payload.refresh_token)
    refresh_record = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        )
    )
    if not refresh_record or refresh_record.is_expired:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid")

    user = db.scalar(select(User).where(User.user_id == refresh_record.user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not available")

    refresh_record.revoked_at = datetime.now(timezone.utc)
    db.add(refresh_record)
    db.flush()
    return _issue_auth_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_user_db)) -> None:
    token_hash = hash_refresh_token(payload.refresh_token)
    refresh_record = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if refresh_record and refresh_record.revoked_at is None:
        refresh_record.revoked_at = datetime.now(timezone.utc)
        db.add(refresh_record)
        db.commit()


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
