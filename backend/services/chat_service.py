"""SellerLens AI — chat-with-your-data service.

Builds a grounded GPT-4o conversation around a seller's processed
settlement data, with short-term session memory and rule-based fallbacks.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections import deque
from typing import Any

from backend.services.azure_openai_service import (
    _build_client,
    _chat_with_retry,
    _format_inr,
)

logger = logging.getLogger("analytics.chat")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are SellerLens AI — a financial assistant for Indian e-commerce sellers. "
    "You have access to this seller's exact settlement data provided in the system context above.\n\n"
    "Rules:\n"
    "- Answer only from the data provided. Never make up numbers.\n"
    "- Use ₹ and Indian number format (1,00,000 not 100,000).\n"
    "- Be direct and specific. No fluff.\n"
    "- If asked something not in the data, say so clearly.\n"
    "- End every answer with one follow-up question suggestion.\n"
    "- Keep answers under 150 words unless detail is needed."
)


# ---------------------------------------------------------------------------
# In-memory session store (last N messages per session_id)
# ---------------------------------------------------------------------------

_MAX_HISTORY = 6  # keeps last 6 messages (3 user / 3 assistant turns)
_SESSION_TTL_SECS = 60 * 60  # 1 hour
_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def _get_session(session_id: str) -> deque:
    """Return the message deque for *session_id*, creating it if needed."""
    now = time.time()
    with _sessions_lock:
        # Lazy expiry sweep
        for sid in list(_sessions.keys()):
            if now - _sessions[sid]["last_seen"] > _SESSION_TTL_SECS:
                del _sessions[sid]

        sess = _sessions.get(session_id)
        if sess is None:
            sess = {"history": deque(maxlen=_MAX_HISTORY), "last_seen": now}
            _sessions[session_id] = sess
        sess["last_seen"] = now
        return sess["history"]


def reset_session(session_id: str) -> None:
    with _sessions_lock:
        _sessions.pop(session_id, None)


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _format_sku_table(skus: list[dict], top_n: int = 8) -> str:
    if not skus:
        return "(no SKU data)"
    top = sorted(skus, key=lambda s: s.get("total_revenue", 0), reverse=True)[:top_n]
    header = f"{'SKU':<20} {'Revenue':>14} {'Net':>14} {'Units':>7} {'Return%':>8}"
    rows = [header, "-" * len(header)]
    for s in top:
        rows.append(
            f"{str(s.get('seller_sku', ''))[:20]:<20} "
            f"{_format_inr(s.get('total_revenue', 0)):>14} "
            f"{_format_inr(s.get('net_settlement', 0)):>14} "
            f"{int(s.get('units_sold', 0)):>7} "
            f"{float(s.get('return_rate', 0)):>7.1f}%"
        )
    return "\n".join(rows)


def _flatten_seller_data(parsed: dict) -> dict:
    """Turn the parser's nested dict into a flat dict for the context template."""
    summary = parsed.get("summary", {}) or {}
    skus = parsed.get("skus", []) or []

    total_orders = summary.get("total_sale_orders", 0) or 0
    total_returns = summary.get("total_returns", 0) or 0
    return_rate = round(total_returns / total_orders * 100, 2) if total_orders else 0

    reclaimable = (
        (summary.get("input_gst_tcs_credits", 0) or 0)
        + (summary.get("income_tax_credits", 0) or 0)
        + abs(summary.get("tcs_amount", 0) or 0)
        + abs(summary.get("tds_amount", 0) or 0)
    )

    best_sku = max(skus, key=lambda s: s.get("net_settlement", 0), default={}).get("seller_sku", "—")
    worst_sku = min(skus, key=lambda s: s.get("net_settlement", 0), default={}).get("seller_sku", "—")

    return {
        "gross_sales": summary.get("gross_sales_amount", 0) or 0,
        "net_settlement": summary.get("net_bank_settlement", 0) or 0,
        "return_rate": return_rate,
        "mp_fees": summary.get("marketplace_fees", 0) or 0,
        "ads_spend": parsed.get("ads_total_spend", 0) or summary.get("ads_fees", 0) or 0,
        "reclaimable": reclaimable,
        "skus": skus,
        "total_orders": total_orders,
        "total_returns": total_returns,
        "best_sku": best_sku,
        "worst_sku": worst_sku,
    }


def build_context(seller_data: dict) -> str:
    """Render the seller's data block that grounds every chat turn."""
    d = _flatten_seller_data(seller_data) if "summary" in seller_data else seller_data

    return f"""SELLER DATA SUMMARY (April 2026):

FINANCIALS:
- Gross Revenue: {_format_inr(d['gross_sales'])}
- Net Settlement: {_format_inr(d['net_settlement'])}
- Return Rate: {d['return_rate']}%
- Marketplace Fees: {_format_inr(d['mp_fees'])}
- Ads Spend: {_format_inr(d['ads_spend'])}
- Reclaimable Credits: {_format_inr(d['reclaimable'])}

SKU PERFORMANCE:
{_format_sku_table(d['skus'])}

ORDER STATS:
- Total orders: {d['total_orders']}
- Total returns: {d['total_returns']}
- Best SKU: {d['best_sku']}
- Worst SKU: {d['worst_sku']}
"""


# ---------------------------------------------------------------------------
# Suggested starter questions
# ---------------------------------------------------------------------------

def suggested_questions(seller_data: dict) -> list[str]:
    """Six starter questions, lightly personalised with real SKU IDs."""
    d = _flatten_seller_data(seller_data) if "summary" in seller_data else seller_data
    skus = d.get("skus", [])
    best = d.get("best_sku") or "your top SKU"
    worst = d.get("worst_sku") or "your worst SKU"

    # Highest return-rate SKU (where return_rate > 0)
    high_return = max(
        (s for s in skus if s.get("return_rate", 0) > 0),
        key=lambda s: s.get("return_rate", 0),
        default=None,
    )
    high_return_sku = high_return.get("seller_sku") if high_return else worst

    return [
        "Which product made me the most money this month?",
        "How much am I losing to returns?",
        f"Why is {high_return_sku} returning so often?",
        "Am I claiming my GST credits correctly?",
        f"Should I stop advertising {worst}?",
        "What would happen if I reduced returns by 10%?",
    ]


# ---------------------------------------------------------------------------
# Data-used extractor
# ---------------------------------------------------------------------------

_CURRENCY_RE = re.compile(r"₹[\d,]+(?:\.\d+)?")
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")


def _extract_data_used(answer: str, seller_data: dict) -> list[dict]:
    """Find SKU IDs and currency figures referenced in the answer."""
    used: list[dict] = []
    seen: set[str] = set()

    # SKU IDs from the data
    skus_data = (
        _flatten_seller_data(seller_data) if "summary" in seller_data else seller_data
    ).get("skus", [])
    for s in skus_data:
        sid = s.get("seller_sku")
        if sid and sid in answer and sid not in seen:
            used.append({"type": "sku", "value": sid})
            seen.add(sid)

    # Currency figures
    for m in _CURRENCY_RE.findall(answer):
        if m not in seen:
            used.append({"type": "amount", "value": m})
            seen.add(m)

    # Percentages (e.g., return rate)
    for m in _PERCENT_RE.findall(answer):
        if m not in seen:
            used.append({"type": "percentage", "value": m})
            seen.add(m)

    return used[:8]


# ---------------------------------------------------------------------------
# Follow-up suggestion extractor
# ---------------------------------------------------------------------------

_QUESTION_RE = re.compile(r"([A-Z][^.?!\n]{8,140}\?)")


def _extract_follow_ups(answer: str, seller_data: dict) -> list[str]:
    """Pull the trailing question (if any) and pad with generic follow-ups."""
    questions = _QUESTION_RE.findall(answer)
    follow_ups = [q.strip() for q in questions[-1:]]  # take the last one

    # Pad with related canned suggestions so the UI always has chips to show
    pool = suggested_questions(seller_data)
    for q in pool:
        if len(follow_ups) >= 3:
            break
        if q not in follow_ups and q not in answer:
            follow_ups.append(q)

    return follow_ups[:3]


# ---------------------------------------------------------------------------
# Public chat function
# ---------------------------------------------------------------------------

def chat(
    question: str,
    session_id: str,
    seller_data: dict,
) -> dict:
    """Answer a seller's natural-language question. Returns the API payload."""
    history = _get_session(session_id)
    context_block = build_context(seller_data)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": context_block},
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": question})

    try:
        client = _build_client()
        content, meta = _chat_with_retry(
            client,
            messages=messages,
            temperature=0.3,
            max_tokens=600,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Chat call failed, using fallback: %s", exc)
        content = _rule_based_answer(question, seller_data)
        meta = {"fallback": True, "error": str(exc)}

    # Persist turn into session memory
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": content})

    return {
        "answer": content,
        "data_used": _extract_data_used(content, seller_data),
        "follow_ups": _extract_follow_ups(content, seller_data),
        "session_id": session_id,
        "_meta": meta,
    }


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def _rule_based_answer(question: str, seller_data: dict) -> str:
    """Deterministic answer for the most common questions when the API is down."""
    d = _flatten_seller_data(seller_data) if "summary" in seller_data else seller_data
    q = question.lower()

    if any(k in q for k in ("most money", "best sku", "top product", "highest revenue")):
        skus = sorted(d["skus"], key=lambda s: s.get("net_settlement", 0), reverse=True)
        if not skus:
            return "I don't have any SKU data yet. Want to upload your latest settlement report?"
        top = skus[0]
        return (
            f"Your top earner is {top['seller_sku']} with net settlement of "
            f"{_format_inr(top['net_settlement'])} from {top.get('units_sold', 0)} units. "
            f"Want me to break down its margin per unit?"
        )

    if any(k in q for k in ("losing to returns", "return cost", "returns hurt")):
        return (
            f"Returns cost you {_format_inr(abs(d['mp_fees']) * 0 + abs(seller_data.get('summary', {}).get('returns_reversal', 0)))} "
            f"this period across {d['total_returns']} returned orders ({d['return_rate']}% return rate). "
            f"Should I show you which SKUs are driving most of the returns?"
        )

    if "gst" in q or "credit" in q or "reclaim" in q:
        return (
            f"You have {_format_inr(d['reclaimable'])} in reclaimable GST/TCS/TDS credits. "
            f"File your GSTR-3B and reconcile Form 26AS to recover these. "
            f"Want me to show the exact breakdown?"
        )

    if "ad" in q or "advertis" in q:
        ratio = (d["ads_spend"] / d["gross_sales"] * 100) if d["gross_sales"] else 0
        return (
            f"You spent {_format_inr(d['ads_spend'])} on ads — that's {ratio:.1f}% of gross sales. "
            f"Healthy ACoS is 8-12%. Want me to flag which campaigns are above that?"
        )

    return (
        f"I can see your gross sales of {_format_inr(d['gross_sales'])} and net settlement of "
        f"{_format_inr(d['net_settlement'])}. Could you ask something more specific — "
        f"for example, about a SKU, returns, fees, or ads?"
    )
