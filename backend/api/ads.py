"""Ads-report API — upload a Flipkart campaign-level report and read analysis.

Endpoints (all require JWT auth and are user-scoped):

  POST /api/upload/ads            upload .csv / .xlsx, returns summary
  GET  /api/ads/analysis          full analysis payload for the active user
  POST /api/ads/insights/refresh  regenerate the AI insights only
  GET  /api/ads/status            quick has-ads check for the UI
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.services.ads_service import (
    apply_category_mapping,
    build_analysis,
    fetch_campaigns,
    has_campaigns,
    parse_ads_file,
    save_campaigns,
)
from backend.services.auth_service import current_user_id

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


def _validate(file: UploadFile, contents: bytes) -> None:
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        name = (file.filename or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")):
            raise HTTPException(
                status_code=400, detail="Only CSV / Excel ads files are accepted."
            )
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Ads file exceeds 25 MB.")


def _run_category_mapping(user_id: int, settlement_period: str | None) -> None:
    """Background task — open its own DB session (the request session is closed by now)."""
    from backend.database import SessionLocal

    db = SessionLocal()
    try:
        apply_category_mapping(db, user_id=user_id, settlement_period=settlement_period)
    except Exception:
        logger.exception("Background category mapping failed for user %s", user_id)
    finally:
        db.close()


@router.post("/upload/ads")
async def upload_ads(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    settlement_period: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Parse a Flipkart ads report and persist its active campaigns."""
    contents = await file.read()
    _validate(file, contents)

    try:
        rows = parse_ads_file(contents, file.filename or "ads.xlsx")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to parse ads file")
        raise HTTPException(
            status_code=400, detail=f"Could not parse ads file: {exc}"
        ) from exc

    uid = int(user_id)
    save_campaigns(db, user_id=uid, rows=rows, settlement_period=settlement_period)

    total_spend = sum(r["ad_spend"] for r in rows)
    total_revenue = sum(r["revenue"] for r in rows)
    active = sum(1 for r in rows if (r.get("campaign_status") or "").upper() == "LIVE")

    # Run the AI category mapper asynchronously so the upload feels snappy.
    background_tasks.add_task(
        _run_category_mapping, uid, settlement_period
    )

    return {
        "filename": file.filename,
        "settlement_period": settlement_period,
        "total_campaigns": len(rows),
        "active_campaigns": active,
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
    }


# ---------------------------------------------------------------------------
# Analysis read endpoints
# ---------------------------------------------------------------------------

@router.get("/ads/analysis")
def ads_analysis(
    settlement_period: str | None = Query(default=None, max_length=100),
    include_insights: bool = Query(default=True),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Return the full ads analysis payload (campaigns + summary + AI insights).

    Pass ``include_insights=false`` to skip the Azure OpenAI call and return
    campaigns + summary immediately (the frontend fetches insights separately).
    """
    return build_analysis(
        db,
        user_id=int(user_id),
        settlement_period=settlement_period,
        include_insights=include_insights,
    )


@router.post("/ads/insights/refresh")
def refresh_ads_insights(
    settlement_period: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    """Re-run the GPT-4o ads-insights generator without re-fetching campaigns."""
    payload = build_analysis(
        db,
        user_id=int(user_id),
        settlement_period=settlement_period,
        include_insights=True,
    )
    return {"ai_insights": payload["ai_insights"]}


@router.get("/ads/status")
def ads_status(
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    uid = int(user_id)
    return {"has_ads": has_campaigns(db, user_id=uid)}
