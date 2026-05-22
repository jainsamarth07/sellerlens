"""User model for email/password + Microsoft SSO authentication.

Lives in its own module so the existing settlement / listing / chat tables
are unaffected. ``ensure_users_table`` lazily creates the table on first
use so no Alembic migration step is required.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint

from backend.database import Base


class User(Base):
    """An authenticated seller account (Microsoft SSO or email/password)."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("microsoft_id", name="uq_users_microsoft_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # NULL for Microsoft SSO users
    business_name = Column(String(255), nullable=True)
    platform = Column(String(50), nullable=False, default="flipkart")
    monthly_revenue_range = Column(String(50), nullable=True)
    auth_provider = Column(String(50), nullable=False, default="email")
    microsoft_id = Column(String(255), nullable=True, index=True)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)


_ensured: set[int] = set()


def ensure_users_table(engine) -> None:
    """Create the ``users`` table on first use (idempotent)."""
    key = id(engine)
    if key in _ensured:
        return
    Base.metadata.create_all(bind=engine, tables=[User.__table__], checkfirst=True)
    _ensured.add(key)
