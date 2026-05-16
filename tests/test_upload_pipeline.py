"""Tests for the async upload pipeline (job tracker + sample data).

These tests deliberately avoid spinning up the full FastAPI app so they don't
depend on SQLAlchemy / Azure SDKs being installed in the test environment.
"""

from __future__ import annotations

import io

import pandas as pd

from backend.services import upload_jobs
from backend.services.sample_data import build_sample_flipkart_workbook


def test_sample_workbook_has_expected_sheets():
    data = build_sample_flipkart_workbook()
    xl = pd.ExcelFile(io.BytesIO(data))
    assert "Summary of report" in xl.sheet_names
    assert "Orders" in xl.sheet_names
    assert "Ads" in xl.sheet_names

    orders = pd.read_excel(xl, sheet_name="Orders", header=1)
    assert len(orders) >= 5
    assert "Seller SKU" in orders.columns
    assert "Sale Amount (Rs.)" in orders.columns


def test_sample_workbook_parses_via_settlement_parser():
    """Round-trip: the sample we hand sellers must parse cleanly."""
    from backend.processors.settlement_parser import parse_settlement

    data = build_sample_flipkart_workbook()
    parsed = parse_settlement(data, "sample.xlsx", "flipkart")

    assert parsed["platform"] == "flipkart"
    assert len(parsed["orders"]) >= 5
    assert parsed["summary"]["gross_sales_amount"] > 0
    assert len(parsed["skus"]) >= 1


def test_job_tracker_lifecycle():
    job = upload_jobs.create_job()
    assert job.status == "processing"
    assert {s.key for s in job.steps} == {"upload", "read", "parse", "profit", "insights"}

    upload_jobs.mark_step(job.job_id, "upload", "done")
    upload_jobs.mark_step(job.job_id, "read", "running")
    snap = upload_jobs.serialize(upload_jobs.get_job(job.job_id))
    steps_by_key = {s["key"]: s for s in snap["steps"]}
    assert steps_by_key["upload"]["status"] == "done"
    assert steps_by_key["read"]["status"] == "running"
    assert snap["status"] == "processing"


def test_job_finish_sets_result():
    job = upload_jobs.create_job()
    upload_jobs.finish_job(job.job_id, {"upload_id": 42})
    snap = upload_jobs.serialize(upload_jobs.get_job(job.job_id))
    assert snap["status"] == "complete"
    assert snap["result"] == {"upload_id": 42}


def test_job_fail_marks_running_step_as_error():
    job = upload_jobs.create_job()
    upload_jobs.mark_step(job.job_id, "parse", "running")
    upload_jobs.fail_job(job.job_id, "boom")
    snap = upload_jobs.serialize(upload_jobs.get_job(job.job_id))
    assert snap["status"] == "error"
    assert snap["error"] == "boom"
    parse_step = next(s for s in snap["steps"] if s["key"] == "parse")
    assert parse_step["status"] == "error"


def test_get_unknown_job_returns_none():
    assert upload_jobs.get_job("does-not-exist") is None
