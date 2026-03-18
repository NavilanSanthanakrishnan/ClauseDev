from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from clauseai_backend.api.deps import get_current_user, get_reference_db, get_user_db
from clauseai_backend.models.auth import User
from clauseai_backend.models.chat import ChatMessage, ChatThread
from clauseai_backend.models.projects import Project
from clauseai_backend.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatThreadCreate,
    ChatThreadResponse,
)
from clauseai_backend.services.chat import build_assistant_reply

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_thread_or_404(db: Session, thread_id: str, user_id: str) -> ChatThread:
    thread = db.scalar(select(ChatThread).where(ChatThread.thread_id == thread_id, ChatThread.user_id == user_id))
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


@router.get("/threads", response_model=list[ChatThreadResponse])
def list_threads(
    db: Session = Depends(get_user_db), current_user: User = Depends(get_current_user)
) -> list[ChatThreadResponse]:
    threads = (
        db.execute(select(ChatThread).where(ChatThread.user_id == current_user.user_id).order_by(ChatThread.updated_at.desc()))
        .scalars()
        .all()
    )
    return [ChatThreadResponse.model_validate(item) for item in threads]


@router.post("/threads", response_model=ChatThreadResponse, status_code=status.HTTP_201_CREATED)
def create_thread(
    payload: ChatThreadCreate,
    db: Session = Depends(get_user_db),
    current_user: User = Depends(get_current_user),
) -> ChatThreadResponse:
    if payload.project_id:
        project = db.scalar(
            select(Project).where(Project.project_id == payload.project_id, Project.user_id == current_user.user_id)
        )
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    scope = "project" if payload.project_id else "general"
    thread = ChatThread(
        thread_id=str(uuid4()),
        user_id=current_user.user_id,
        project_id=payload.project_id,
        title=payload.title,
        scope=scope,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return ChatThreadResponse.model_validate(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageResponse])
def list_messages(
    thread_id: str,
    db: Session = Depends(get_user_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessageResponse]:
    _get_thread_or_404(db, thread_id, current_user.user_id)
    messages = (
        db.execute(select(ChatMessage).where(ChatMessage.thread_id == thread_id).order_by(ChatMessage.created_at.asc()))
        .scalars()
        .all()
    )
    return [
        ChatMessageResponse(
            message_id=item.message_id,
            role=item.role,
            content=item.content,
            citations=list(item.citations),
            created_at=item.created_at,
        )
        for item in messages
    ]


@router.post("/threads/{thread_id}/messages", response_model=list[ChatMessageResponse], status_code=status.HTTP_201_CREATED)
def create_message(
    thread_id: str,
    payload: ChatMessageCreate,
    user_db: Session = Depends(get_user_db),
    reference_db: Session = Depends(get_reference_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessageResponse]:
    thread = _get_thread_or_404(user_db, thread_id, current_user.user_id)

    user_message = ChatMessage(
        message_id=str(uuid4()),
        thread_id=thread.thread_id,
        role="user",
        content=payload.content,
        citations=[],
    )
    user_db.add(user_message)

    assistant_content, citations = build_assistant_reply(
        user_db=user_db,
        reference_db=reference_db,
        thread=thread,
        user_message=payload.content,
    )
    assistant_message = ChatMessage(
        message_id=str(uuid4()),
        thread_id=thread.thread_id,
        role="assistant",
        content=assistant_content,
        citations=citations,
    )
    user_db.add(assistant_message)
    thread.updated_at = datetime.now(timezone.utc)
    user_db.add(thread)
    user_db.commit()
    return [
        ChatMessageResponse(
            message_id=user_message.message_id,
            role=user_message.role,
            content=user_message.content,
            citations=[],
            created_at=user_message.created_at,
        ),
        ChatMessageResponse(
            message_id=assistant_message.message_id,
            role=assistant_message.role,
            content=assistant_message.content,
            citations=list(assistant_message.citations),
            created_at=assistant_message.created_at,
        ),
    ]
