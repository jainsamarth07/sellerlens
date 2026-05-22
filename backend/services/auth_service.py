"""Authentication helpers — JWT, password hashing, and MSAL Microsoft SSO.

All MSAL configuration is read lazily from environment variables so the
auth module imports cleanly even when no Microsoft App Registration has
been provisioned yet (the email/password flow still works in that case).
"""

from __future__ import annotations

import datetime
import os
import secrets
from typing import Any

import jwt
import requests
from fastapi import Depends, Header, HTTPException, status
import bcrypt
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User, ensure_users_table


# ---------------------------------------------------------------------------
# Settings (env-driven, with safe defaults so import never fails in tests)
# ---------------------------------------------------------------------------

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-insecure-change-me")
JWT_ALG = "HS256"
JWT_EXPIRY_DAYS = 7

MS_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "")
MS_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "")
MS_TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID", "common")
MS_REDIRECT_URI = os.environ.get(
    "MICROSOFT_REDIRECT_URI", "http://localhost:5173/auth/callback"
)
MS_AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
MS_SCOPES = ["User.Read"]

GRAPH_ME_URL = "https://graph.microsoft.com/v1.0/me"


# ---------------------------------------------------------------------------
# Password hashing (bcrypt, 12 rounds; passwords >72 bytes are pre-hashed
# with SHA-256 so the bcrypt 72-byte limit doesn't truncate them silently)
# ---------------------------------------------------------------------------

import hashlib

_BCRYPT_ROUNDS = 12


def _to_bcrypt_bytes(plain: str) -> bytes:
    raw = plain.encode("utf-8")
    if len(raw) > 72:
        # Pre-hash long passwords so we don't silently drop entropy.
        raw = hashlib.sha256(raw).hexdigest().encode("ascii")
    return raw


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(_to_bcrypt_bytes(plain), salt).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, email: str) -> str:
    now = datetime.datetime.utcnow()
    payload = {
        "user_id": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(days=JWT_EXPIRY_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI auth dependency
# ---------------------------------------------------------------------------

def _strip_bearer(value: str) -> str:
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value.strip()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — resolves the authenticated :class:`User` from the
    ``Authorization: Bearer <jwt>`` header. Raises 401 otherwise."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header"
        )
    payload = decode_token(_strip_bearer(authorization))
    user_id = payload.get("user_id")
    if not isinstance(user_id, int):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )
    ensure_users_table(db.get_bind())
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def current_user_id(user: User = Depends(get_current_user)) -> str:
    """Convenience dep that returns the stringified user id for storage layers
    keyed by a ``user_id`` :class:`str` (chat sessions, listing products…)."""
    return str(user.id)


# ---------------------------------------------------------------------------
# Microsoft SSO via MSAL
# ---------------------------------------------------------------------------

def _msal_client():
    """Build (lazily) an MSAL ``ConfidentialClientApplication``.

    Returns ``None`` if Microsoft credentials aren't configured — callers
    should respond with a friendly 503 in that case.
    """
    if not MS_CLIENT_ID or not MS_CLIENT_SECRET:
        return None
    import msal  # imported lazily so optional dep doesn't break tests

    return msal.ConfidentialClientApplication(
        client_id=MS_CLIENT_ID,
        client_credential=MS_CLIENT_SECRET,
        authority=MS_AUTHORITY,
    )


def generate_state() -> str:
    return secrets.token_urlsafe(24)


def build_microsoft_auth_url(state: str) -> str:
    """Build the OAuth2 authorization-code URL the browser is redirected to."""
    client = _msal_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Microsoft SSO is not configured on the server.",
        )
    return client.get_authorization_request_url(
        scopes=MS_SCOPES,
        redirect_uri=MS_REDIRECT_URI,
        state=state,
    )


def exchange_microsoft_code(code: str) -> dict[str, Any]:
    """Exchange an authorization code for an access token + Graph profile."""
    client = _msal_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Microsoft SSO is not configured on the server.",
        )
    result = client.acquire_token_by_authorization_code(
        code, scopes=MS_SCOPES, redirect_uri=MS_REDIRECT_URI
    )
    if "access_token" not in result:
        raise HTTPException(
            status_code=400,
            detail=result.get("error_description") or "Microsoft token exchange failed",
        )

    profile = _fetch_graph_profile(result["access_token"])
    return {"token": result, "profile": profile}


def _fetch_graph_profile(access_token: str) -> dict[str, Any]:
    resp = requests.get(
        GRAPH_ME_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"Microsoft Graph error ({resp.status_code})",
        )
    return resp.json()
