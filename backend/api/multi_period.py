"""Multi-period analysis API."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.seller_data import SellerUpload
from backend.services.auth_service import current_user_id
from backend.services.multi_period_analyzer import analyze_multi_period

router = APIRouter()


class MultiPeriodRequest(BaseModel):
    upload_ids: list[int]


@router.post("/multi-period")
async def multi_period_from_uploads(
    body: MultiPeriodRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Run multi-period analysis using already-stored upload data — no re-parsing needed."""
    if len(body.upload_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 uploads required.")
    if len(body.upload_ids) > 6:
        raise HTTPException(status_code=400, detail="Maximum 6 uploads.")

    uploads = (
        db.query(SellerUpload)
        .filter(
            SellerUpload.user_id == int(user_id),
            SellerUpload.id.in_(body.upload_ids),
            SellerUpload.summary_json.isnot(None),
        )
        .all()
    )

    if len(uploads) < 2:
        raise HTTPException(
            status_code=400,
            detail="Not enough stored uploads found. Please upload each settlement file first.",
        )

    parsed_files = []
    for u in uploads:
        parsed_files.append({
            "summary": json.loads(u.summary_json),
            "skus": json.loads(u.skus_json or "[]"),
            "ads_total_spend": u.ads_total_spend or 0.0,
            "platform": u.platform,
        })

    return await run_in_threadpool(analyze_multi_period, parsed_files)
