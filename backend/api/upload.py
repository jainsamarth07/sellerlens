"""File upload endpoints — accept CSV / Excel from sellers.

Two modes are supported:

1. Synchronous ``POST /api/upload/`` — original behaviour, returns the parsed
   payload directly (used by simple components like the top-bar uploader).
2. Async pipeline:
   - ``POST /api/upload/start``  → immediately returns a ``job_id``
   - ``GET  /api/upload/status/{job_id}`` → poll every 1-2s for step progress
   - ``GET  /api/upload/sample`` → download a sample Flipkart workbook
"""

from __future__ import annotations

import threading

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database import SessionLocal, get_db
from backend.models.seller_data import SellerUpload
from backend.processors.settlement_parser import parse_settlement
from backend.services import upload_jobs
from backend.services.sample_data import build_sample_flipkart_workbook
from backend.services.storage import StorageService

router = APIRouter()

ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # browsers sometimes send this for .xlsx
}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _validate(file: UploadFile, contents: bytes) -> None:
    if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
        name = (file.filename or "").lower()
        if not (name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")):
            raise HTTPException(
                status_code=400,
                detail="Only CSV and Excel files are accepted.",
            )
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit.")


def _build_upload_response(
    upload_id: int, filename: str | None, parsed: dict, blob_url: str
) -> dict:
    rows = len(parsed.get("orders", []))
    errs = parsed.get("parsing_errors", [])
    return {
        "upload_id": upload_id,
        "filename": filename,
        "platform": parsed.get("platform"),
        "rows_parsed": rows,
        "rows_total": rows + len(errs),
        "summary": parsed.get("summary"),
        "ads_total_spend": parsed.get("ads_total_spend"),
        "skus": parsed.get("skus", [])[:50],
        "parsing_errors": errs,
        "blob_url": blob_url,
    }


# ---------------------------------------------------------------------------
# Synchronous upload (legacy / simple use)
# ---------------------------------------------------------------------------


@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    platform: str = "flipkart",
    db: Session = Depends(get_db),
):
    """Upload, parse, and persist a settlement report in a single round-trip."""
    contents = await file.read()
    _validate(file, contents)

    storage = StorageService()
    try:
        blob_url = storage.upload_blob(file.filename or "upload.csv", contents)
    except Exception:  # noqa: BLE001
        blob_url = ""

    parsed = parse_settlement(contents, file.filename or "upload.csv", platform)

    upload_record = SellerUpload(
        filename=file.filename,
        platform=parsed.get("platform", platform),
        blob_url=blob_url,
        row_count=len(parsed.get("orders", [])),
    )
    db.add(upload_record)
    db.commit()
    db.refresh(upload_record)

    return _build_upload_response(upload_record.id, file.filename, parsed, blob_url)


# ---------------------------------------------------------------------------
# Async pipeline
# ---------------------------------------------------------------------------


def _run_pipeline(job_id: str, contents: bytes, filename: str, platform: str) -> None:
    """Execute the upload pipeline, updating job status as each step completes."""
    upload_jobs.mark_step(job_id, "upload", "done")

    db = SessionLocal()
    try:
        upload_jobs.mark_step(job_id, "read", "running")
        try:
            storage = StorageService()
            blob_url = storage.upload_blob(filename, contents)
            upload_jobs.mark_step(job_id, "read", "done")
        except Exception as exc:  # noqa: BLE001
            blob_url = ""
            upload_jobs.mark_step(
                job_id, "read", "done", detail=f"local mode ({exc.__class__.__name__})"
            )

        upload_jobs.mark_step(job_id, "parse", "running")
        parsed = parse_settlement(contents, filename, platform)
        rows = len(parsed.get("orders", []))
        upload_jobs.mark_step(job_id, "parse", "done", detail=f"{rows} transactions")

        upload_jobs.mark_step(job_id, "profit", "running")
        sku_count = len(parsed.get("skus", []))
        upload_jobs.mark_step(job_id, "profit", "done", detail=f"{sku_count} SKUs analysed")

        upload_jobs.mark_step(job_id, "insights", "running")
        upload_jobs.mark_step(job_id, "insights", "done", detail="ready on dashboard")

        upload_record = SellerUpload(
            filename=filename,
            platform=parsed.get("platform", platform),
            blob_url=blob_url,
            row_count=rows,
        )
        db.add(upload_record)
        db.commit()
        db.refresh(upload_record)

        result = _build_upload_response(upload_record.id, filename, parsed, blob_url)
        upload_jobs.finish_job(job_id, result)
    except Exception as exc:  # noqa: BLE001
        upload_jobs.fail_job(job_id, str(exc))
    finally:
        db.close()


@router.post("/start")
async def start_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    platform: str = "flipkart",
):
    """Kick off background processing and return a ``job_id`` for polling."""
    contents = await file.read()
    _validate(file, contents)

    job = upload_jobs.create_job()
    threading.Thread(
        target=_run_pipeline,
        args=(job.job_id, contents, file.filename or "upload.xlsx", platform),
        daemon=True,
    ).start()

    return {"job_id": job.job_id, "status": "processing"}


@router.get("/status/{job_id}")
async def get_status(job_id: str):
    job = upload_jobs.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    return upload_jobs.serialize(job)


# ---------------------------------------------------------------------------
# Sample download
# ---------------------------------------------------------------------------


@router.get("/sample")
async def download_sample():
    """Return a small valid Flipkart settlement workbook so sellers see the format."""
    data = build_sample_flipkart_workbook()
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="sellerlens-sample.xlsx"'},
    )
