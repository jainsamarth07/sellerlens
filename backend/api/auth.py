"""Authentication endpoints — Microsoft Entra ID SSO + email/password.

Mounted under ``/api/auth``. All routes are public except ``/me``, which
requires a valid JWT. State for the Microsoft OAuth flow is held in a
small in-memory dict (single-process / dev appropriate; for prod-scale
sessions move this to Redis).
"""

from __future__ import annotations

import datetime
import logging
import threading
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.ads import AdCampaign
from backend.models.chat import ChatMessage, ChatSession
from backend.models.listing import ListingProduct
from backend.models.seller_data import OrderRow, SellerUpload
from backend.models.user import User, ensure_users_table
from backend.services.auth_service import (
    MS_REDIRECT_URI,
    build_microsoft_auth_url,
    current_user_id,
    create_access_token,
    exchange_microsoft_code,
    generate_state,
    get_current_user,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    business_name: str | None = Field(default=None, max_length=255)
    platform: str | None = Field(default="flipkart", max_length=50)
    monthly_revenue_range: str | None = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    email: str
    business_name: str | None
    platform: str | None
    monthly_revenue_range: str | None
    auth_provider: str
    avatar_url: str | None
    is_new_user: bool = False


class AuthResponse(BaseModel):
    token: str
    user: UserOut


# ---------------------------------------------------------------------------
# In-memory OAuth state cache (CSRF protection)
# ---------------------------------------------------------------------------

_state_cache: dict[str, float] = {}
_state_lock = threading.Lock()
_STATE_TTL = 600  # 10 minutes


def _remember_state(state: str) -> None:
    now = datetime.datetime.utcnow().timestamp()
    with _state_lock:
        # expire old states
        for k in list(_state_cache.keys()):
            if now - _state_cache[k] > _STATE_TTL:
                _state_cache.pop(k, None)
        _state_cache[state] = now


def _consume_state(state: str) -> bool:
    with _state_lock:
        ts = _state_cache.pop(state, None)
    if ts is None:
        return False
    return (datetime.datetime.utcnow().timestamp() - ts) <= _STATE_TTL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_out(user: User, *, is_new: bool = False) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        business_name=user.business_name,
        platform=user.platform,
        monthly_revenue_range=user.monthly_revenue_range,
        auth_provider=user.auth_provider,
        avatar_url=user.avatar_url,
        is_new_user=is_new,
    )


def _frontend_callback_url(token: str, *, is_new: bool) -> str:
    """Build the SPA redirect URL with the JWT in the hash fragment.

    The frontend callback page reads ``window.location.hash``; using the
    fragment ensures the token is never logged by the server / proxies.
    """
    base = MS_REDIRECT_URI.split("#", 1)[0]
    fragment = urlencode({"token": token, "new": "1" if is_new else "0"})
    return f"{base}#{fragment}"


# ---------------------------------------------------------------------------
# Email / password endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=AuthResponse)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    ensure_users_table(db.get_bind())
    email = body.email.lower()

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.auth_provider == "microsoft" or existing.microsoft_id:
            raise HTTPException(
                status_code=400,
                detail="This email is linked to a Microsoft account. Use Microsoft login.",
            )
        raise HTTPException(status_code=400, detail="Email already registered.")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        business_name=body.business_name,
        platform=body.platform or "flipkart",
        monthly_revenue_range=body.monthly_revenue_range,
        auth_provider="email",
        last_login=datetime.datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return AuthResponse(token=token, user=_user_out(user, is_new=True))


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    ensure_users_table(db.get_bind())
    email = body.email.lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user.auth_provider == "microsoft":
        raise HTTPException(
            status_code=400,
            detail="This account uses Microsoft login. Click 'Sign in with Microsoft'.",
        )
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user.last_login = datetime.datetime.utcnow()
    db.commit()

    token = create_access_token(user.id, user.email)
    return AuthResponse(token=token, user=_user_out(user))


# ---------------------------------------------------------------------------
# Microsoft SSO
# ---------------------------------------------------------------------------

@router.get("/microsoft/login")
def microsoft_login():
    """Return the Microsoft OAuth2 authorization URL for the SPA to redirect to."""
    state = generate_state()
    _remember_state(state)
    url = build_microsoft_auth_url(state=state)
    return {"auth_url": url, "state": state}


@router.get("/microsoft/callback")
def microsoft_callback(code: str, state: str, db: Session = Depends(get_db)):
    if not _consume_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    exchanged = exchange_microsoft_code(code)
    profile: dict[str, Any] = exchanged["profile"]

    ms_id = profile.get("id")
    email = (profile.get("mail") or profile.get("userPrincipalName") or "").lower()
    display_name = profile.get("displayName")

    if not ms_id or not email:
        raise HTTPException(status_code=400, detail="Microsoft profile missing id or email.")

    ensure_users_table(db.get_bind())
    user = db.query(User).filter(User.microsoft_id == ms_id).first()
    is_new = False
    if user is None:
        # Match by email too (sometimes the same person signed up with email first)
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                business_name=display_name,
                auth_provider="microsoft",
                microsoft_id=ms_id,
                avatar_url=None,
                last_login=datetime.datetime.utcnow(),
            )
            db.add(user)
            is_new = True
        else:
            # Link existing email account to Microsoft
            user.microsoft_id = ms_id
            user.auth_provider = "microsoft"
            if not user.business_name:
                user.business_name = display_name
            user.last_login = datetime.datetime.utcnow()
    else:
        user.last_login = datetime.datetime.utcnow()
        if display_name and not user.business_name:
            user.business_name = display_name

    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    return RedirectResponse(_frontend_callback_url(token, is_new=is_new), status_code=302)


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.post("/logout")
def logout():
    """Stateless logout — the client discards the JWT. Returns 200 always."""
    return {"status": "ok"}


@router.post("/data/clear")
def clear_user_data(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Delete all persisted data owned by the authenticated user."""
    uid = int(user_id)

    uploads = (
        db.query(SellerUpload.id)
        .filter(SellerUpload.user_id == uid)
        .all()
    )
    upload_ids = [row[0] for row in uploads]
    deleted_orders = 0
    deleted_uploads = 0
    if upload_ids:
        deleted_orders = (
            db.query(OrderRow)
            .filter(OrderRow.upload_id.in_(upload_ids))
            .delete(synchronize_session=False)
        )
        deleted_uploads = (
            db.query(SellerUpload)
            .filter(SellerUpload.id.in_(upload_ids))
            .delete(synchronize_session=False)
        )

    deleted_ads = (
        db.query(AdCampaign)
        .filter(AdCampaign.user_id == uid)
        .delete(synchronize_session=False)
    )

    deleted_listing = (
        db.query(ListingProduct)
        .filter(ListingProduct.user_id == user_id)
        .delete(synchronize_session=False)
    )

    sessions = (
        db.query(ChatSession.id)
        .filter(ChatSession.user_id == user_id)
        .all()
    )
    session_ids = [row[0] for row in sessions]
    deleted_messages = 0
    deleted_sessions = 0
    if session_ids:
        deleted_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id.in_(session_ids))
            .delete(synchronize_session=False)
        )
        deleted_sessions = (
            db.query(ChatSession)
            .filter(ChatSession.id.in_(session_ids))
            .delete(synchronize_session=False)
        )

    db.commit()
    return {
        "status": "ok",
        "deleted": {
            "uploads": deleted_uploads,
            "orders": deleted_orders,
            "ad_campaigns": deleted_ads,
            "listing_products": deleted_listing,
            "chat_sessions": deleted_sessions,
            "chat_messages": deleted_messages,
        },
    }
