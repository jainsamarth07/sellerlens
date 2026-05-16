"""Tests for the chat-with-your-data service."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services import chat_service as cs


SAMPLE_DATA = {
    "summary": {
        "gross_sales_amount": 200000,
        "net_bank_settlement": 140000,
        "total_sale_orders": 100,
        "total_returns": 12,
        "returns_reversal": -25000,
        "marketplace_fees": -50000,
        "tcs_amount": -2000,
        "tds_amount": -1000,
        "input_gst_tcs_credits": 5000,
        "income_tax_credits": 1000,
    },
    "ads_total_spend": 30000,
    "skus": [
        {"seller_sku": "BB-101-BLK-01", "total_revenue": 150000, "net_settlement": 100000,
         "units_sold": 50, "return_rate": 18, "total_orders": 60, "return_orders": 11},
        {"seller_sku": "AA-200-RED-02", "total_revenue": 50000, "net_settlement": 40000,
         "units_sold": 25, "return_rate": 4, "total_orders": 25, "return_orders": 1},
    ],
}


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

class TestBuildContext:
    def test_includes_required_sections(self):
        ctx = cs.build_context(SAMPLE_DATA)
        assert "FINANCIALS" in ctx
        assert "SKU PERFORMANCE" in ctx
        assert "ORDER STATS" in ctx
        # Indian-formatted figures
        assert "₹2,00,000" in ctx
        assert "₹1,40,000" in ctx
        # SKU rendered
        assert "BB-101-BLK-01" in ctx

    def test_handles_empty_data(self):
        ctx = cs.build_context({"summary": {}, "skus": [], "ads_total_spend": 0})
        assert "₹0.00" in ctx
        assert "(no SKU data)" in ctx


# ---------------------------------------------------------------------------
# Suggested questions
# ---------------------------------------------------------------------------

class TestSuggestedQuestions:
    def test_returns_six_questions(self):
        qs = cs.suggested_questions(SAMPLE_DATA)
        assert len(qs) == 6
        for q in qs:
            assert q.endswith("?")

    def test_personalises_with_high_return_sku(self):
        qs = cs.suggested_questions(SAMPLE_DATA)
        # BB-101-BLK-01 has the highest return rate, should appear in the prompt
        assert any("BB-101-BLK-01" in q for q in qs)


# ---------------------------------------------------------------------------
# Session memory
# ---------------------------------------------------------------------------

class TestSessionMemory:
    def setup_method(self):
        cs._sessions.clear()

    def test_history_capped(self):
        sid = "test-session-1"
        h = cs._get_session(sid)
        for i in range(20):
            h.append({"role": "user", "content": str(i)})
        # maxlen=6 so only last 6 retained
        assert len(h) == 6
        assert h[-1]["content"] == "19"

    def test_reset(self):
        sid = "reset-me"
        cs._get_session(sid).append({"role": "user", "content": "hi"})
        assert sid in cs._sessions
        cs.reset_session(sid)
        assert sid not in cs._sessions


# ---------------------------------------------------------------------------
# Data-used and follow-up extractors
# ---------------------------------------------------------------------------

class TestExtractors:
    def test_extracts_skus_and_amounts(self):
        answer = (
            "Your top earner is BB-101-BLK-01 with net settlement of ₹1,00,000 "
            "and a return rate of 18%."
        )
        used = cs._extract_data_used(answer, SAMPLE_DATA)
        types = {u["type"] for u in used}
        assert "sku" in types
        assert "amount" in types
        assert "percentage" in types

    def test_follow_ups_uses_trailing_question(self):
        answer = "Your top SKU is BB-101-BLK-01. Want me to break down its margin per unit?"
        ups = cs._extract_follow_ups(answer, SAMPLE_DATA)
        assert ups[0].endswith("?")
        assert "margin per unit" in ups[0]


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

class TestRuleBasedAnswers:
    def test_top_product(self):
        ans = cs._rule_based_answer("Which product made me the most money?", SAMPLE_DATA)
        assert "BB-101-BLK-01" in ans  # highest net_settlement
        assert "₹" in ans

    def test_returns_question(self):
        ans = cs._rule_based_answer("How much am I losing to returns?", SAMPLE_DATA)
        assert "₹" in ans
        assert "12" in ans  # total_returns count

    def test_gst_question(self):
        ans = cs._rule_based_answer("Am I claiming GST credits correctly?", SAMPLE_DATA)
        assert "GST" in ans or "credit" in ans.lower()

    def test_unknown_question_helpful(self):
        ans = cs._rule_based_answer("What is the meaning of life?", SAMPLE_DATA)
        assert "₹" in ans  # references actual data


# ---------------------------------------------------------------------------
# Full chat path with mocked Azure client
# ---------------------------------------------------------------------------

def _mock_response(text: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = text
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 80
    return response


class TestChatFlow:
    def setup_method(self):
        cs._sessions.clear()

    def test_chat_returns_payload_and_persists_history(self):
        fake_client = MagicMock()
        fake_client.chat.completions.create.return_value = _mock_response(
            "Your top SKU is BB-101-BLK-01 earning ₹1,00,000. Want a per-unit margin breakdown?"
        )

        with patch.object(cs, "_build_client", return_value=fake_client):
            r1 = cs.chat("Which product made the most money?", "sess-1", SAMPLE_DATA)

        assert "BB-101-BLK-01" in r1["answer"]
        assert any(d["type"] == "sku" for d in r1["data_used"])
        assert r1["follow_ups"]
        assert r1["session_id"] == "sess-1"
        # History should now have 2 entries (user + assistant)
        assert len(cs._sessions["sess-1"]["history"]) == 2

    def test_fallback_when_api_fails(self):
        with patch.object(cs, "_build_client", side_effect=RuntimeError("offline")):
            r = cs.chat("Which product made the most money?", "sess-fb", SAMPLE_DATA)
        assert "BB-101-BLK-01" in r["answer"]
        assert r["_meta"]["fallback"] is True
