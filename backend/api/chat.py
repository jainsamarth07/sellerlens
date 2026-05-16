"""Chat-with-your-data API — POST /api/chat."""

from __future__ import annotations

import json
import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.seller_data import SellerUpload
from backend.processors.settlement_parser import parse_settlement
from backend.services.chat_service import (
    chat as chat_service,
    reset_session,
    suggested_questions,
)
from backend.services.storage import StorageService

router = APIRouter()


# ---------------------------------------------------------------------------
# Tiny per-upload parsed-data cache so each chat turn doesn't re-parse Excel
# ---------------------------------------------------------------------------

_parsed_cache: dict[int, dict] = {}
_cache_lock = threading.Lock()


def _load_seller_data(upload_id: int, db: Session) -> dict:
    """Load (and cache) the parsed settlement data for *upload_id*."""
    with _cache_lock:
        cached = _parsed_cache.get(upload_id)
    if cached is not None:
        return cached

    record = db.query(SellerUpload).filter(SellerUpload.id == upload_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"Upload {upload_id} not found")

    storage = StorageService()
    blob_bytes = storage.download_blob(record.blob_url)
    parsed = parse_settlement(blob_bytes, record.filename or "", record.platform)

    with _cache_lock:
        _parsed_cache[upload_id] = parsed
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
async def chat_endpoint(body: ChatRequest, db: Session = Depends(get_db)):
    """Answer a seller's natural-language question, grounded in their data."""
    seller_data = body.seller_data
    if seller_data is None:
        if body.upload_id is None:
            raise HTTPException(
                status_code=400,
                detail="Provide either seller_data or upload_id.",
            )
        seller_data = _load_seller_data(body.upload_id, db)

    result = chat_service(body.question, body.session_id, seller_data)
    return ChatResponse(
        answer=result["answer"],
        data_used=result["data_used"],
        follow_ups=result["follow_ups"],
        session_id=result["session_id"],
    )


@router.get("/suggestions/{upload_id}")
async def get_suggestions(upload_id: int, db: Session = Depends(get_db)):
    """Return six personalised starter questions for the chat UI."""
    seller_data = _load_seller_data(upload_id, db)
    return {"questions": suggested_questions(seller_data)}


@router.post("/suggestions")
async def post_suggestions(seller_data: dict):
    """Same as GET above but takes the parsed data directly (no DB lookup)."""
    return {"questions": suggested_questions(seller_data)}


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear the in-memory chat history for a session."""
    reset_session(session_id)
    return {"status": "cleared", "session_id": session_id}
