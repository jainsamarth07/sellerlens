"""Tests for the optional Flipkart listing-file ingestion (additive feature).

Uses an in-memory SQLite database so the suite has no PostgreSQL dependency.
"""

from __future__ import annotations

import io

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.listing import DEFAULT_USER_ID, ListingProduct  # noqa: F401 — register table
from backend.services.listing_service import (
    LISTING_COLUMNS,
    ensure_listing_table,
    listing_lookup,
    match_summary,
    parse_listing_file,
    resolve_sku_names,
    save_listings,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    """Fresh in-memory SQLite session per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[ListingProduct.__table__])
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_listing_workbook(rows: list[dict]) -> bytes:
    """Build a .xlsx that mirrors the real Flipkart listing-export header row."""
    cols = list(LISTING_COLUMNS.values())
    df = pd.DataFrame([{c: r.get(_inverse(c)) for c in cols} for r in rows])
    # Add an extra unrelated column so we exercise resilience to extra fields.
    df["Some unrelated column"] = "ignored"
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Sheet1", index=False)
    return buf.getvalue()


def _inverse(display_name: str) -> str:
    for k, v in LISTING_COLUMNS.items():
        if v == display_name:
            return k
    raise KeyError(display_name)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestParseListingFile:
    def test_extracts_expected_columns(self):
        wb = _make_listing_workbook([
            {
                "sku": "ARNIC250_1",
                "product_name": "Arnica Hair Oil 250ml",
                "mrp": 499,
                "selling_price": 379,
                "current_stock": 42,
                "status": "ACTIVE",
                "category": "haircare",
            },
            {
                "sku": "BCCRE50C_1",
                "product_name": "Skin Radiance Cream 50g",
                "mrp": 799,
                "selling_price": 569,
                "current_stock": 0,
                "status": "INACTIVE",
                "category": "skin_treatment",
            },
        ])
        rows = parse_listing_file(wb, "Sunova Listing.xlsx")
        assert len(rows) == 2
        first = rows[0]
        assert first["sku"] == "ARNIC250_1"
        assert first["product_name"] == "Arnica Hair Oil 250ml"
        assert first["mrp"] == 499.0
        assert first["selling_price"] == 379.0
        assert first["current_stock"] == 42
        assert first["status"] == "ACTIVE"
        assert first["category"] == "haircare"

    def test_missing_required_column_raises(self):
        df = pd.DataFrame([{"Wrong Header": "x"}])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Sheet1", index=False)
        with pytest.raises(ValueError):
            parse_listing_file(buf.getvalue(), "broken.xlsx")

    def test_skips_blank_and_duplicate_skus(self):
        wb = _make_listing_workbook([
            {"sku": "S1", "product_name": "First", "status": "ACTIVE"},
            {"sku": "", "product_name": "Skipped"},
            {"sku": "S1", "product_name": "Duplicate ignored"},
            {"sku": "S2", "product_name": "Second"},
        ])
        rows = parse_listing_file(wb, "x.xlsx")
        assert [r["sku"] for r in rows] == ["S1", "S2"]


# ---------------------------------------------------------------------------
# Persistence & resolution
# ---------------------------------------------------------------------------

class TestSaveAndResolve:
    def test_save_then_resolve(self, db):
        wb = _make_listing_workbook([
            {"sku": "ARNIC250_1", "product_name": "Arnica Hair Oil",
             "mrp": 499, "selling_price": 379, "current_stock": 42, "status": "ACTIVE"},
            {"sku": "BCCRE50C_1", "product_name": "Skin Radiance Cream",
             "mrp": 799, "selling_price": 569, "current_stock": 0, "status": "INACTIVE"},
        ])
        save_listings(db, DEFAULT_USER_ID, parse_listing_file(wb, "x.xlsx"))

        skus = [
            {"seller_sku": "ARNIC250_1", "total_revenue": 1000.0},
            {"seller_sku": "UNKNOWN_SKU", "total_revenue": 200.0},
        ]
        enriched = resolve_sku_names(skus, db, user_id=DEFAULT_USER_ID)

        assert enriched[0]["product_name"] == "Arnica Hair Oil"
        assert enriched[0]["current_stock"] == 42
        assert enriched[0]["listing_status"] == "ACTIVE"
        # Unknown SKU → keys present but None so frontend can fall back.
        assert enriched[1]["product_name"] is None
        assert enriched[1]["current_stock"] is None

    def test_upsert_overwrites_existing(self, db):
        save_listings(db, DEFAULT_USER_ID, [
            {"sku": "S1", "product_name": "Old name", "mrp": 100,
             "selling_price": 90, "current_stock": 10, "status": "ACTIVE",
             "category": "x"},
        ])
        save_listings(db, DEFAULT_USER_ID, [
            {"sku": "S1", "product_name": "New name", "mrp": 200,
             "selling_price": 180, "current_stock": 5, "status": "INACTIVE",
             "category": "y"},
        ])
        lookup = listing_lookup(db, DEFAULT_USER_ID)
        assert lookup["S1"]["product_name"] == "New name"
        assert lookup["S1"]["current_stock"] == 5

    def test_resolve_without_db_is_safe(self):
        skus = [{"seller_sku": "S1"}]
        out = resolve_sku_names(skus, db=None)
        assert out[0]["product_name"] is None
        assert "current_stock" in out[0]

    def test_match_summary(self, db):
        save_listings(db, DEFAULT_USER_ID, [
            {"sku": "MATCH1", "product_name": "x"},
            {"sku": "MATCH2", "product_name": "y"},
        ])
        result = match_summary(db, DEFAULT_USER_ID, ["MATCH1", "MATCH2", "MISS", "MATCH1"])
        assert result["matched"] == 3  # 2x MATCH1 + 1x MATCH2 found
        assert result["total"] == 4
        assert result["unmatched_skus"] == ["MISS"]
        assert result["listing_count"] == 2

    def test_ensure_table_is_idempotent(self, db):
        ensure_listing_table(db.get_bind())
        ensure_listing_table(db.get_bind())  # second call must not raise
