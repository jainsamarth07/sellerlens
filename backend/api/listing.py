"""POST /api/upload/listing — optional Flipkart listing-file ingest.

Provides:
  - POST /api/upload/listing       upload an .xlsx/.csv listing file
  - GET  /api/upload/listing/status see how many products are currently mapped
  - POST /api/upload/listing/match  return {matched/total/unmatched} for an
                                    arbitrary SKU list (used by the dashboard
                                    badge after a settlement upload)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.listing import DEFAULT_USER_ID, ListingProduct
from backend.services.auth_service import current_user_id
from backend.services.listing_service import (
    ensure_listing_table,
    listing_lookup,
    match_summary,
    parse_listing_file,
    save_listings,
)

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB — listings are smaller than settlements


def _validate(file: UploadFile, contents: bytes) -> None:
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        name = (file.filename or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")):
            raise HTTPException(status_code=400, detail="Only CSV / Excel files are accepted.")
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Listing file exceeds 25 MB.")


class MatchRequest(BaseModel):
    sku_codes: list[str]


@router.post("/listing")
async def upload_listing(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Parse and upsert a Flipkart listing file. Returns count + total."""
    contents = await file.read()
    _validate(file, contents)

    try:
        rows = parse_listing_file(contents, file.filename or "listing.xlsx")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to parse listing file")
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    written = save_listings(db, user_id=user_id, rows=rows)
    return {
        "filename": file.filename,
        "matched": written,        # rows persisted from this file
        "total": len(rows),        # rows parsed from this file
        "unmatched_skus": [],      # listing upload itself can't be unmatched
        "listing_count": _count(db, user_id),
    }


@router.get("/listing/status")
async def listing_status(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """How many listing products this user has uploaded — drives the UI badge."""
    try:
        ensure_listing_table(db.get_bind())
        count = _count(db, user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("listing_status fallback: %s", exc)
        count = 0
    return {"user_id": user_id, "listing_count": count, "has_listing": count > 0}


@router.post("/listing/match")
async def listing_match(
    req: MatchRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """For a given SKU list, report how many resolve to a listing product."""
    return match_summary(db, user_id=user_id, sku_codes=req.sku_codes)


@router.get("/listing/products")
async def listing_products(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Return the full sku→product map for the active user (used by the frontend)."""
    return {"user_id": user_id, "products": listing_lookup(db, user_id=user_id)}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count(db: Session, user_id: str) -> int:
    ensure_listing_table(db.get_bind())
    return int(
        db.execute(
            select(func.count(ListingProduct.id)).where(ListingProduct.user_id == user_id)
        ).scalar_one()
    )
