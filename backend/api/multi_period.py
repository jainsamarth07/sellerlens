"""Multi-period analysis API — accepts up to 6 settlement files at once."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from backend.processors.settlement_parser import parse_settlement
from backend.services.auth_service import get_current_user
from backend.services.multi_period_analyzer import analyze_multi_period

router = APIRouter()

_MAX_FILES = 6


@router.post("/multi-period")
async def multi_period_analysis(
    files: list[UploadFile] = File(...),
    _user=Depends(get_current_user),
):
    """Upload 2-6 settlement files and return a multi-period analysis."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file required.")
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {_MAX_FILES} files per request.",
        )

    parsed_files: list[dict] = []
    for f in files:
        contents = await f.read()
        parsed = await run_in_threadpool(parse_settlement, contents, f.filename or "upload", None)
        parsed_files.append(parsed)

    return await run_in_threadpool(analyze_multi_period, parsed_files)
