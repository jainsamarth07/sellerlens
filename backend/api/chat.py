"""Chat-with-your-data API — POST /api/chat."""

from __future__ import annotations

import json
import threading
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.seller_data import SellerUpload
from backend.processors.settlement_parser import parse_settlement
from backend.services.auth_service import current_user_id, get_current_user
from backend.services.chat_service import (
    chat as chat_service,
    reset_session,
    suggested_questions,
)
from backend.services.storage import StorageService

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tiny per-upload parsed-data cache so each chat turn doesn't re-parse Excel
# ---------------------------------------------------------------------------

_parsed_cache: dict[tuple[int, int], dict] = {}
_cache_lock = threading.Lock()


def _load_seller_data(upload_id: int, db: Session, user_id: int) -> dict:
    """Load (and cache) the parsed settlement data for *upload_id*.

    The upload **must** belong to ``user_id`` — we never trust a frontend
    supplied identifier. Returns 404 if the upload doesn't exist or
    belongs to someone else (intentionally ambiguous to avoid leaking
    existence of other sellers' uploads).
    """
    record = (
        db.query(SellerUpload)
        .filter(SellerUpload.id == upload_id, SellerUpload.user_id == user_id)
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Upload {upload_id} not found")

    cache_key = (user_id, upload_id)
    with _cache_lock:
        cached = _parsed_cache.get(cache_key)
    if cached is not None:
        return cached

    storage = StorageService()
    blob_bytes = storage.download_blob(record.blob_url)
    parsed = parse_settlement(blob_bytes, record.filename or "", record.platform)

    with _cache_lock:
        _parsed_cache[cache_key] = parsed
    return parsed


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    session_id: str = Field(..., min_length=1, max_length=128)
    upload_id: int | None = None
    seller_data: dict | None = None  # allow direct payload (skips DB lookup)


class DataChip(BaseModel):
    type: str
    value: str


class ChatResponse(BaseModel):
    answer: str
    data_used: list[DataChip]
    follow_ups: list[str]
    session_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ChatResponse)
@router.post("/", response_model=ChatResponse)
async def chat_endpoint(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Answer a seller's natural-language question, grounded in their data.

    The data context is *always* fetched / verified server-side using the
    authenticated ``user_id`` from the JWT — never from any frontend
    supplied identifier. ``seller_data`` from the request body is only
    accepted as a convenience cache and re-scoped via ``upload_id``.
    """
    seller_data = body.seller_data
    if body.upload_id is not None:
        # Prefer server-side reload from storage for fresh data. If that fails
        # (for example local/no-blob mode), fall back to client-sent seller_data
        # so chat fallback logic can still answer.
        try:
            seller_data = _load_seller_data(body.upload_id, db, int(user_id))
        except HTTPException as exc:
            # Keep auth/ownership and request-shape errors strict.
            if exc.status_code in {400, 401, 403, 404}:
                raise
            if body.seller_data is None:
                raise
            logger.warning(
                "chat data reload failed for upload_id=%s (status=%s); using request seller_data",
                body.upload_id,
                exc.status_code,
            )
            seller_data = body.seller_data
        except Exception as exc:  # noqa: BLE001
            if body.seller_data is None:
                raise
            logger.warning(
                "chat data reload exception for upload_id=%s; using request seller_data: %s",
                body.upload_id,
                exc,
            )
            seller_data = body.seller_data
    elif seller_data is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either seller_data or upload_id.",
        )

    result = chat_service(body.question, body.session_id, seller_data)
    return ChatResponse(
        answer=result["answer"],
        data_used=result["data_used"],
        follow_ups=result["follow_ups"],
        session_id=result["session_id"],
    )


@router.get("/suggestions/{upload_id}")
async def get_suggestions(
    upload_id: int,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Return six personalised starter questions for the chat UI."""
    seller_data = _load_seller_data(upload_id, db, int(user_id))
    return {"questions": suggested_questions(seller_data)}


@router.post("/suggestions")
async def post_suggestions(
    seller_data: dict, _user=Depends(get_current_user)
):
    """Same as GET above but takes the parsed data directly (no DB lookup)."""
    return {"questions": suggested_questions(seller_data)}


@router.delete("/session/{session_id}")
async def clear_session(session_id: str, _user=Depends(get_current_user)):
    """Clear the in-memory chat history for a session."""
    reset_session(session_id)
    return {"status": "cleared", "session_id": session_id}
