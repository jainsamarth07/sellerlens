"""Tests for the Flipkart ads-report ingestion + analytics service.

Verifies:
  * .xlsx and .csv parsing (skipping the two metadata header rows)
  * Filtering out campaigns with Ad Spend = 0
  * Per-user + per-period replacement on re-upload
  * Verdict thresholds (star / decent / watch / stop)
  * Summary aggregation (totals, wasted, best/worst)
  * Category cross-reference (joins ads with settlement SKUs)
  * Cross-user isolation — Bob never sees Alice's campaigns
"""

from __future__ import annotations

import io

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models.ads import AdCampaign  # noqa: F401 — register table
from backend.services.ads_service import (
    ADS_COLUMNS,
    _category_cross_ref,
    _summary,
    _row_to_dict,
    build_chat_context_block,
    ensure_ads_table,
    fetch_campaigns,
    has_campaigns,
    parse_ads_file,
    save_campaigns,
    verdict_for,
)


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AdCampaign.__table__])
    Session = sessionmaker(bind=engine, autoflush=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_ads_xlsx(rows: list[dict]) -> bytes:
    """Build a .xlsx that mimics Flipkart's two-metadata-rows-on-top layout.

    Real export has rows: [metadata-1, metadata-2, header, data...]. We use
    pandas with ``header=2`` to read it, so we need two filler rows followed
    by the real column header.
    """
    cols = list(ADS_COLUMNS.values())
    df = pd.DataFrame(
        [{c: r.get(_inv(c)) for c in cols} for r in rows]
    )
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        # Two metadata rows + a blank row before our real header? No — the
        # parser uses header=2 which means rows 0 & 1 are skipped and row 2
        # becomes the column header. Write 2 metadata rows manually, then the
        # header + data.
        sheet = "istuff365dec"
        meta = pd.DataFrame([["Report"], ["Generated"]])
        meta.to_excel(w, sheet_name=sheet, index=False, header=False)
        df.to_excel(
            w, sheet_name=sheet, index=False, startrow=2, header=True
        )
    return buf.getvalue()


def _make_ads_csv(rows: list[dict]) -> bytes:
    cols = list(ADS_COLUMNS.values())
    df = pd.DataFrame([{c: r.get(_inv(c)) for c in cols} for r in rows])
    buf = io.StringIO()
    buf.write("Report metadata line 1\n")
    buf.write("Report metadata line 2\n")
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("latin1")


def _inv(display: str) -> str:
    for k, v in ADS_COLUMNS.items():
        if v == display:
            return k
    raise KeyError(display)


def _campaign(**overrides) -> dict:
    """Default valid campaign dict for tests."""
    base = {
        "campaign_id": "C1",
        "campaign_name": "Default Campaign",
        "campaign_status": "LIVE",
        "budget_type": "DAILY",
        "campaign_budget": 1000.0,
        "ad_spend": 500.0,
        "views": 1000,
        "clicks": 50,
        "conversions": 10.0,
        "revenue": 2500.0,
        "roi": 5.0,
        "ctr": 0.05,
        "conversion_rate": 0.2,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

class TestParseAdsFile:
    def test_xlsx_filters_zero_spend(self):
        wb = _make_ads_xlsx([
            _campaign(campaign_id="A", ad_spend=500),
            _campaign(campaign_id="B", ad_spend=0),  # historical — dropped
            _campaign(campaign_id="C", ad_spend=120.5),
        ])
        rows = parse_ads_file(wb, "december.xlsx")
        assert len(rows) == 2
        assert {r["campaign_id"] for r in rows} == {"A", "C"}

    def test_csv_skiprows_2(self):
        csv_bytes = _make_ads_csv([
            _campaign(campaign_id="X", ad_spend=200.0),
            _campaign(campaign_id="Y", ad_spend=0.0),
        ])
        rows = parse_ads_file(csv_bytes, "report.csv")
        assert len(rows) == 1
        assert rows[0]["campaign_id"] == "X"

    def test_missing_required_column_raises(self):
        df = pd.DataFrame([{"Campaign ID": "C", "Campaign Name": "n"}])
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            pd.DataFrame([["meta"], ["meta"]]).to_excel(
                w, sheet_name="s", index=False, header=False
            )
            df.to_excel(w, sheet_name="s", index=False, startrow=2)
        with pytest.raises(ValueError, match="Ad Spend"):
            parse_ads_file(buf.getvalue(), "bad.xlsx")


# ---------------------------------------------------------------------------
# Persistence + user isolation
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_save_replaces_existing_period(self, db):
        ensure_ads_table(db.get_bind())
        save_campaigns(db, user_id=1, rows=[_campaign(campaign_id="A")], settlement_period="dec")
        save_campaigns(db, user_id=1, rows=[_campaign(campaign_id="B")], settlement_period="dec")
        out = fetch_campaigns(db, user_id=1, settlement_period="dec")
        assert [c.campaign_id for c in out] == ["B"]

    def test_user_isolation(self, db):
        ensure_ads_table(db.get_bind())
        save_campaigns(db, user_id=1, rows=[_campaign(campaign_id="A")])
        save_campaigns(db, user_id=2, rows=[_campaign(campaign_id="B")])

        alice = fetch_campaigns(db, user_id=1)
        bob = fetch_campaigns(db, user_id=2)

        assert [c.campaign_id for c in alice] == ["A"]
        assert [c.campaign_id for c in bob] == ["B"]
        assert has_campaigns(db, user_id=1)
        assert has_campaigns(db, user_id=99) is False


# ---------------------------------------------------------------------------
# Verdicts + summary
# ---------------------------------------------------------------------------

class TestVerdict:
    @pytest.mark.parametrize(
        "roi,revenue,expected",
        [
            (10.0, 5000, "star"),
            (8.0, 5000, "star"),
            (7.99, 5000, "decent"),
            (4.0, 5000, "decent"),
            (3.99, 5000, "watch"),
            (2.0, 5000, "watch"),
            (1.99, 5000, "stop"),
            (10.0, 0, "stop"),  # zero revenue ⇒ stop regardless of ROI
        ],
    )
    def test_thresholds(self, roi, revenue, expected):
        assert verdict_for(roi, revenue) == expected


class TestSummary:
    def test_aggregates_totals_wasted_and_extremes(self):
        rows = [
            _row_to_dict(
                AdCampaign(
                    id=1, user_id=1, campaign_id="A", campaign_name="A",
                    campaign_status="LIVE", ad_spend=1000, revenue=10000,
                    roi=10, ctr=0.05, conversion_rate=0.2,
                )
            ),
            _row_to_dict(
                AdCampaign(
                    id=2, user_id=1, campaign_id="B", campaign_name="B",
                    campaign_status="PAUSED", ad_spend=500, revenue=0,
                    roi=0, ctr=0, conversion_rate=0,
                )
            ),
            _row_to_dict(
                AdCampaign(
                    id=3, user_id=1, campaign_id="C", campaign_name="C",
                    campaign_status="LIVE", ad_spend=300, revenue=300,
                    roi=1.0, ctr=0.01, conversion_rate=0.01,
                )
            ),
        ]
        s = _summary(rows)
        assert s["total_spend"] == 1800.0
        assert s["total_revenue"] == 10300.0
        assert s["overall_roi"] == round(10300 / 1800, 4)
        assert s["wasted_spend"] == 500.0
        assert s["wasted_campaigns"] == 1
        assert s["best_campaign"]["name"] == "A"
        assert s["worst_campaign"]["name"] == "B"
        assert s["active_campaigns"] == 2  # only LIVE
        assert s["total_campaigns"] == 3
        assert "B" in s["campaigns_to_stop"]


# ---------------------------------------------------------------------------
# Category cross-reference
# ---------------------------------------------------------------------------

class TestCategoryCrossRef:
    def test_joins_ads_with_settlement_skus(self):
        ad_rows = [
            {"campaign_name": "Bag promo", "ad_spend": 1000, "revenue": 4000,
             "roi": 4, "mapped_category": "bag"},
            {"campaign_name": "Cable promo", "ad_spend": 500, "revenue": 100,
             "roi": 0.2, "mapped_category": "data_cable"},
        ]
        skus = [
            {"seller_sku": "BAG-1", "category": "bag", "total_revenue": 20000},
            {"seller_sku": "CBL-1", "category": "data_cable", "total_revenue": 3000},
        ]
        out = _category_cross_ref(ad_rows, skus)
        by_cat = {r["category"]: r for r in out}

        assert by_cat["bag"]["ad_spend"] == 1000.0
        assert by_cat["bag"]["settlement_revenue"] == 20000.0
        assert by_cat["bag"]["verdict"] == "efficient"  # 5% < 10%

        assert by_cat["data_cable"]["verdict"] == "unclear" or by_cat["data_cable"][
            "verdict"
        ] == "unclear"
        # Cable: 500 / 3000 = 16.7% → unclear (between 10% and 20%)
        assert 16 < by_cat["data_cable"]["ad_cost_ratio_pct"] < 17


# ---------------------------------------------------------------------------
# Chat-context helper
# ---------------------------------------------------------------------------

class TestChatContextBlock:
    def test_returns_none_when_no_ads(self, db):
        ensure_ads_table(db.get_bind())
        assert build_chat_context_block(db, user_id=42) is None

    def test_includes_summary_when_ads_present(self, db):
        ensure_ads_table(db.get_bind())
        save_campaigns(
            db,
            user_id=7,
            rows=[
                _campaign(campaign_id="A", campaign_name="Top", ad_spend=1000, revenue=10000, roi=10),
                _campaign(campaign_id="B", campaign_name="Dud", ad_spend=500, revenue=0, roi=0),
            ],
        )
        block = build_chat_context_block(db, user_id=7)
        assert block is not None
        assert "ADS SUMMARY" in block
        assert "Total Ad Spend" in block
        assert "Top" in block
