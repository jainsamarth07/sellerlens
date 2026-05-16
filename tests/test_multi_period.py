"""Tests for the multi-period settlement analyzer."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from backend.services import multi_period_analyzer as mp


def _make_period(payment_duration: str, *, gross: float, net: float,
                 orders: int, returns: int, mp_fees: float, ads: float,
                 skus: list[dict]) -> dict:
    return {
        "summary": {
            "payment_duration": payment_duration,
            "gross_sales_amount": gross,
            "net_bank_settlement": net,
            "total_sale_orders": orders,
            "total_returns": returns,
            "marketplace_fees": mp_fees,
            "tcs_amount": -1000,
            "tds_amount": -500,
            "input_gst_tcs_credits": 2000,
            "income_tax_credits": 500,
            "ads_fees": ads,
        },
        "ads_total_spend": ads,
        "skus": skus,
    }


@pytest.fixture
def four_periods():
    sku_a = lambda rev, ret, units: {
        "seller_sku": "SKU-A",
        "total_revenue": rev, "net_settlement": rev * 0.7,
        "return_rate": ret, "units_sold": units,
    }
    sku_b = lambda rev, ret, units: {
        "seller_sku": "SKU-B",
        "total_revenue": rev, "net_settlement": rev * 0.6,
        "return_rate": ret, "units_sold": units,
    }
    return [
        _make_period("Jan 2026", gross=100000, net=70000, orders=80, returns=8,
                     mp_fees=-20000, ads=10000,
                     skus=[sku_a(80000, 5, 40), sku_b(20000, 6, 10)]),
        _make_period("Feb 2026", gross=120000, net=82000, orders=95, returns=10,
                     mp_fees=-22000, ads=12000,
                     skus=[sku_a(85000, 6, 45), sku_b(35000, 8, 18)]),
        _make_period("Mar 2026", gross=140000, net=95000, orders=110, returns=14,
                     mp_fees=-24000, ads=15000,
                     skus=[sku_a(70000, 9, 38), sku_b(70000, 5, 35)]),
        _make_period("Apr 2026", gross=160000, net=110000, orders=130, returns=12,
                     mp_fees=-26000, ads=16000,
                     skus=[sku_a(60000, 12, 30), sku_b(100000, 4, 50)]),
    ]


# ---------------------------------------------------------------------------
# Period parsing
# ---------------------------------------------------------------------------

class TestPeriodParsing:
    @pytest.mark.parametrize("text,expected_month", [
        ("Apr 2026", 4),
        ("April 2026", 4),
        ("01-Apr-2026 to 15-Apr-2026", 4),
        ("01/04/2026 to 15/04/2026", 4),
    ])
    def test_parse_period(self, text, expected_month):
        dt = mp._parse_period(text)
        assert dt is not None
        assert dt.month == expected_month
        assert dt.year == 2026

    def test_unknown_returns_none(self):
        # Truly garbage strings return None
        assert mp._parse_period("") is None


# ---------------------------------------------------------------------------
# Trend math
# ---------------------------------------------------------------------------

class TestTrendMath:
    def test_compare_growth(self):
        c = mp._compare(120, 100)
        assert c["change_abs"] == 20
        assert c["change_pct"] == 20.0
        assert c["trend"] == "up"

    def test_compare_decline_lower_better(self):
        c = mp._compare(8.0, 10.0, lower_is_better=True)
        # Decline in a "lower-is-better" metric is a good thing
        assert c["trend"] == "down-good"

    def test_compare_flat(self):
        c = mp._compare(100, 100.5)
        assert c["trend"] == "flat"

    def test_consecutive_declines(self):
        assert mp._consecutive_declines([100, 90, 80, 70]) == 3
        assert mp._consecutive_declines([100, 110, 90, 80]) == 2
        assert mp._consecutive_declines([100, 110, 120]) == 0

    def test_classify_trend(self):
        assert mp._classify_trend([100, 200], lower_is_better=False) == "growing"
        assert mp._classify_trend([200, 100], lower_is_better=False) == "declining"
        assert mp._classify_trend([10, 5], lower_is_better=True) == "improving"
        assert mp._classify_trend([5, 10], lower_is_better=True) == "worsening"


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

class TestAnalyzeMultiPeriod:
    @pytest.fixture
    def result(self, four_periods):
        # Force the rule-based AI fallback so tests are hermetic
        with patch.object(mp, "_build_client", side_effect=RuntimeError("offline")):
            return mp.analyze_multi_period(four_periods)

    def test_periods_sorted_chronologically(self, result):
        assert result["periods"] == ["Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026"]

    def test_metrics_time_series(self, result):
        assert result["metrics"]["revenue"] == [100000, 120000, 140000, 160000]
        assert result["metrics"]["net_settlement"] == [70000, 82000, 95000, 110000]
        assert len(result["metrics"]["return_rate"]) == 4

    def test_pop_comparison(self, result):
        pop = result["pop_comparison"]
        assert pop["gross_revenue"]["current"] == 160000
        assert pop["gross_revenue"]["previous"] == 140000
        assert pop["gross_revenue"]["trend"] == "up"
        # Best SKU changed from SKU-A in earlier periods to SKU-B in April
        assert pop["best_sku"]["changed"] is True

    def test_best_and_worst_month(self, result):
        assert result["best_month"] == "Apr 2026"
        assert result["worst_month"] == "Jan 2026"

    def test_sku_trends_include_decline_flag(self, result):
        trends = {t["seller_sku"]: t for t in result["sku_trends"]}
        # SKU-A revenue: 80k -> 85k -> 70k -> 60k → declining for last 2 periods
        assert trends["SKU-A"]["consecutive_decline_months"] >= 2
        assert trends["SKU-A"]["flag_declining"] is True
        # SKU-B revenue: 20k -> 35k -> 70k -> 100k → growing
        assert trends["SKU-B"]["revenue_trend"] == "growing"
        assert trends["SKU-B"]["flag_declining"] is False

    def test_ai_trend_analysis_fallback_shape(self, result):
        ai = result["ai_trend_analysis"]
        assert {"growing_or_declining", "most_improved_metric",
                "needs_urgent_attention", "next_month_prediction",
                "biggest_impact_action"} <= ai.keys()
        assert ai["_meta"]["fallback"] is True

    def test_handles_single_period(self):
        with patch.object(mp, "_build_client", side_effect=RuntimeError("offline")):
            r = mp.analyze_multi_period([_make_period("Apr 2026", gross=100, net=70, orders=10, returns=1,
                                                       mp_fees=-20, ads=10, skus=[])])
        assert r["periods"] == ["Apr 2026"]
        assert r["pop_comparison"] == {}
        assert r["ai_trend_analysis"] == {}

    def test_caps_at_six_files(self):
        many = [_make_period(f"M{i} 2026", gross=100, net=70, orders=10, returns=1,
                             mp_fees=-20, ads=10, skus=[]) for i in range(10)]
        # Use month names that parse so the dates sort properly
        many = [_make_period(label, gross=100, net=70, orders=10, returns=1,
                             mp_fees=-20, ads=10, skus=[])
                for label in ["Jan 2026", "Feb 2026", "Mar 2026", "Apr 2026",
                              "May 2026", "Jun 2026", "Jul 2026"]]
        with patch.object(mp, "_build_client", side_effect=RuntimeError("offline")):
            r = mp.analyze_multi_period(many)
        assert r["period_count"] == 6


# ---------------------------------------------------------------------------
# AI path with mocked client
# ---------------------------------------------------------------------------

class TestAiPath:
    def test_ai_response_parsed(self, four_periods, monkeypatch):
        from unittest.mock import MagicMock

        payload = {
            "growing_or_declining": "growing — revenue up 60%",
            "most_improved_metric": "Net Settlement (+57%)",
            "needs_urgent_attention": "Return rate creeping up",
            "next_month_prediction": "Revenue likely ₹1,80,000",
            "biggest_impact_action": "Scale SKU-B ads by 25%",
        }
        import json

        fake_client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = json.dumps(payload)
        response.usage.prompt_tokens = 200
        response.usage.completion_tokens = 150
        fake_client.chat.completions.create.return_value = response

        with patch.object(mp, "_build_client", return_value=fake_client):
            result = mp.analyze_multi_period(four_periods)

        ai = result["ai_trend_analysis"]
        assert ai["growing_or_declining"].startswith("growing")
        assert ai["_meta"]["input_tokens"] == 200
