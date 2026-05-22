"""SQLAlchemy models for persisted chat sessions and messages.

Separate file from ``seller_data`` / ``listing`` so the existing tables are
not touched. Tables are created on demand via :func:`ensure_chat_tables`.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.database import Base

DEFAULT_USER_ID = "default"


def _uuid() -> str:
    return str(uuid.uuid4())


class ChatSession(Base):
    """One persisted chat conversation (per settlement period / user)."""

    __tablename__ = "chat_sessions"
    __table_args__ = (Index("ix_chat_sessions_user", "user_id"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(64), nullable=False, default=DEFAULT_USER_ID, index=True)
    settlement_period = Column(String(100), nullable=True)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatMessage(Base):
    """A single message inside a :class:`ChatSession`."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_session", "session_id"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    session = relationship("ChatSession", back_populates="messages")


_ensured_engines: set[int] = set()


def ensure_chat_tables(engine) -> None:
    """Idempotently create ``chat_sessions`` and ``chat_messages`` tables."""
    key = id(engine)
    if key in _ensured_engines:
        return
    Base.metadata.create_all(
        bind=engine,
        tables=[ChatSession.__table__, ChatMessage.__table__],
        checkfirst=True,
    )
    _ensured_engines.add(key)
