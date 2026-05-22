"""Persisted chat-session CRUD endpoints.

Mounted at ``/api/chat`` (alongside the existing chat endpoints) so the
frontend can hydrate / sync conversations across tab switches and reloads.
The Azure OpenAI call structure in :mod:`backend.services.chat_service`
is untouched.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import engine, get_db
from backend.models.chat import (
    DEFAULT_USER_ID,
    ChatMessage,
    ChatSession,
    ensure_chat_tables,
)
from backend.services.auth_service import current_user_id

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    period: str | None = Field(default=None, max_length=100)
    user_id: str | None = Field(default=None, max_length=64)


class SessionOut(BaseModel):
    id: str
    label: str | None
    settlement_period: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageCreate(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure() -> None:
    ensure_chat_tables(engine)


def _user(user_id: str | None) -> str:
    return user_id or DEFAULT_USER_ID


def _get_session_or_404(db: Session, session_id: str, user_id: str) -> ChatSession:
    session = (
        db.query(ChatSession)
        .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    _ensure()
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return [
        SessionOut(
            id=s.id,
            label=s.label,
            settlement_period=s.settlement_period,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=len(s.messages),
        )
        for s in sessions
    ]


@router.post("/sessions", response_model=SessionOut)
def create_session(
    body: SessionCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    _ensure()
    session = ChatSession(
        user_id=user_id,
        label=body.label or "New chat",
        settlement_period=body.period,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return SessionOut(
        id=session.id,
        label=session.label,
        settlement_period=session.settlement_period,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=0,
    )


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    _ensure()
    session = _get_session_or_404(db, session_id, user_id)
    return [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
        )
        for m in session.messages
    ]


@router.post("/sessions/{session_id}/messages", response_model=MessageOut)
def add_message(
    session_id: str,
    body: MessageCreate,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    _ensure()
    session = _get_session_or_404(db, session_id, user_id)
    msg = ChatMessage(session_id=session.id, role=body.role, content=body.content)
    db.add(msg)
    session.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return MessageOut(id=msg.id, role=msg.role, content=msg.content, created_at=msg.created_at)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    _ensure()
    session = _get_session_or_404(db, session_id, user_id)
    db.delete(session)
    db.commit()
    return {"status": "deleted", "session_id": session_id}
