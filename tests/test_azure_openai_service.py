"""Tests for the AI analysis engine — covers the rule-based fallback path
and the JSON-parsing wrapper. The Azure OpenAI client is monkey-patched so
no live API call is made.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services import azure_openai_service as svc


# ---------------------------------------------------------------------------
# Indian formatter
# ---------------------------------------------------------------------------

class TestFormatInr:
    @pytest.mark.parametrize("value,expected", [
        (0, "₹0.00"),
        (100, "₹100.00"),
        (1000, "₹1,000.00"),
        (12345, "₹12,345.00"),
        (123456, "₹1,23,456.00"),
        (12345678, "₹1,23,45,678.00"),
        (-12345, "₹-12,345.00"),
    ])
    def test_indian_grouping(self, value, expected):
        assert svc._format_inr(value) == expected


# ---------------------------------------------------------------------------
# Rule-based fallback (no API)
# ---------------------------------------------------------------------------

class TestRuleBasedInsights:
    def _settlement(self, **overrides):
        base = {
            "summary": {
                "gross_sales_amount": 200000,
                "net_bank_settlement": 140000,
                "total_sale_orders": 100,
                "total_returns": 15,
                "returns_reversal": -25000,
                "marketplace_fees": -50000,
                "tcs_amount": -2000,
                "tds_amount": -1000,
                "input_gst_tcs_credits": 5000,
                "income_tax_credits": 1000,
            },
            "ads_total_spend": 35000,
            "skus": [
                {"seller_sku": "SKU-A", "total_revenue": 150000, "net_settlement": 100000,
                 "units_sold": 50, "return_rate": 18, "net_per_unit": 2000},
                {"seller_sku": "SKU-B", "total_revenue": 50000, "net_settlement": 40000,
                 "units_sold": 25, "return_rate": 4, "net_per_unit": 1600},
            ],
        }
        base["summary"].update(overrides)
        return base

    def test_fallback_returns_full_shape(self):
        # Force the fallback path by raising in the API call
        with patch.object(svc, "_build_client", side_effect=RuntimeError("offline")):
            result = svc.generate_seller_insights(self._settlement())

        assert "insights" in result
        assert len(result["insights"]) == 5
        for i in result["insights"]:
            assert i["type"] in {"warning", "opportunity", "info"}
            assert {"title", "finding", "action", "rupee_impact"} <= i.keys()
        assert 0 <= result["health_score"] <= 100
        assert result["health_label"] in {"Healthy", "Needs Attention", "Critical"}
        assert isinstance(result["one_line_summary"], str)
        assert result["_meta"]["fallback"] is True

    def test_fallback_flags_high_return_rate(self):
        with patch.object(svc, "_build_client", side_effect=RuntimeError("offline")):
            result = svc.generate_seller_insights(self._settlement())
        titles = [i["title"].lower() for i in result["insights"]]
        assert any("return" in t for t in titles)

    def test_fallback_flags_concentration_risk(self):
        # SKU-A is 75% of revenue → should be flagged
        with patch.object(svc, "_build_client", side_effect=RuntimeError("offline")):
            result = svc.generate_seller_insights(self._settlement())
        findings = " ".join(i["finding"].lower() for i in result["insights"])
        assert "concentration" in findings or "top sku" in findings


class TestRuleBasedSku:
    def test_loss_maker(self):
        sku = {"seller_sku": "X", "total_revenue": 1000, "net_settlement": -500,
               "units_sold": 10, "return_rate": 12, "net_per_unit": -50,
               "total_orders": 10, "return_orders": 1,
               "avg_selling_price": 100, "total_mp_fees": -200, "total_refunds": -100}
        with patch.object(svc, "_build_client", side_effect=RuntimeError("offline")):
            r = svc.analyze_sku(sku)
        assert r["verdict"] == "loss-maker"
        assert "pause" in r["action_item"].lower() or "discontinue" in r["pricing_recommendation"].lower()

    def test_star(self):
        sku = {"seller_sku": "Y", "total_revenue": 50000, "net_settlement": 30000,
               "units_sold": 100, "return_rate": 3, "net_per_unit": 300,
               "total_orders": 100, "return_orders": 3,
               "avg_selling_price": 500, "total_mp_fees": -5000, "total_refunds": 0}
        with patch.object(svc, "_build_client", side_effect=RuntimeError("offline")):
            r = svc.analyze_sku(sku)
        assert r["verdict"] == "star"
        assert r["ad_spend_verdict"] in {"scale", "worth it"}


# ---------------------------------------------------------------------------
# Successful API path with mocked client
# ---------------------------------------------------------------------------

def _mock_chat_response(json_payload: dict) -> MagicMock:
    """Build a fake AzureOpenAI chat completion response object."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(json_payload)
    response.usage.prompt_tokens = 250
    response.usage.completion_tokens = 400
    return response


class TestApiPath:
    def test_generate_insights_parses_json(self):
        payload = {
            "insights": [
                {"type": "warning", "title": "Test", "finding": "f", "action": "a", "rupee_impact": "₹100"}
            ] * 5,
            "health_score": 72,
            "health_label": "Needs Attention",
            "one_line_summary": "Doing okay.",
        }
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _mock_chat_response(payload)

        with patch.object(svc, "_build_client", return_value=fake_client):
            result = svc.generate_seller_insights({"summary": {}, "skus": [], "ads_total_spend": 0})

        assert result["health_score"] == 72
        assert result["health_label"] == "Needs Attention"
        assert "_meta" in result
        assert result["_meta"]["input_tokens"] == 250
        assert result["_meta"]["output_tokens"] == 400
        assert result["_meta"]["cost_inr"] > 0

    def test_safe_json_loads_strips_fences(self):
        wrapped = "```json\n{\"a\": 1}\n```"
        assert svc._safe_json_loads(wrapped) == {"a": 1}
