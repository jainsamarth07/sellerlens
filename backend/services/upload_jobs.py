"""In-memory async job tracker for the upload-and-process pipeline.

This is intentionally simple — single-process, dictionary-backed. For a
hackathon / demo it's enough; for production replace with Redis or a DB.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobStep:
    key: str
    label: str
    status: str = "pending"  # pending | running | done | error
    detail: str = ""


@dataclass
class UploadJob:
    job_id: str
    status: str = "processing"  # processing | complete | error
    steps: list[JobStep] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)


_jobs: dict[str, UploadJob] = {}
_lock = threading.Lock()

DEFAULT_STEPS = [
    ("upload", "File uploaded securely"),
    ("read", "Reading report structure"),
    ("parse", "Parsing transactions"),
    ("profit", "Calculating profit per SKU"),
    ("insights", "Generating AI insights"),
]


def create_job() -> UploadJob:
    """Register a new job with the default 5-step pipeline."""
    job = UploadJob(
        job_id=uuid.uuid4().hex[:12],
        steps=[JobStep(key=k, label=l) for k, l in DEFAULT_STEPS],
    )
    with _lock:
        _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> UploadJob | None:
    with _lock:
        return _jobs.get(job_id)


def mark_step(job_id: str, key: str, status: str, detail: str = "") -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        for step in job.steps:
            if step.key == key:
                step.status = status
                if detail:
                    step.detail = detail
                break


def finish_job(job_id: str, result: dict[str, Any]) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = "complete"
        job.result = result


def fail_job(job_id: str, message: str) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return
        job.status = "error"
        job.error = message
        for step in job.steps:
            if step.status == "running":
                step.status = "error"


def serialize(job: UploadJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "status": job.status,
        "error": job.error,
        "steps": [
            {"key": s.key, "label": s.label, "status": s.status, "detail": s.detail}
            for s in job.steps
        ],
        "result": job.result,
    }
