"""Multi-period settlement analyzer.

Takes 2–6 parsed settlement reports (different months) and produces:
- Period-over-period metric comparisons
- SKU-level trend tracking
- AI-generated trend narrative (with rule-based fallback)
- Dashboard-ready time series
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from backend.services.azure_openai_service import (
    _build_client,
    _chat_with_retry,
    _format_inr,
    _safe_json_loads,
)

logger = logging.getLogger("analytics.multi_period")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Period detection
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_DATE_RE = re.compile(r"(\d{1,2})[-/\s](\d{1,2}|[A-Za-z]+)[-/\s](\d{2,4})")
_MONTH_YEAR_RE = re.compile(r"([A-Za-z]+)[\s\-]*(\d{4})")


def _parse_period(text: str) -> datetime | None:
    """Extract a representative date from a free-text payment_duration string."""
    if not text:
        return None
    text = text.strip()

    # Try "Apr 2026" / "April-2026"
    m = _MONTH_YEAR_RE.search(text)
    if m:
        month_str, year_str = m.group(1).lower(), m.group(2)
        if month_str in _MONTHS:
            return datetime(int(year_str), _MONTHS[month_str], 1)

    # Try "01-Apr-2026" / "01/04/2026"
    m = _DATE_RE.search(text)
    if m:
        day, month_part, year = m.groups()
        try:
            year_int = int(year)
            if year_int < 100:
                year_int += 2000
            month_int = (
                _MONTHS.get(month_part.lower())
                if not month_part.isdigit()
                else int(month_part)
            )
            if month_int and 1 <= month_int <= 12:
                return datetime(year_int, month_int, int(day))
        except (ValueError, TypeError):
            pass

    # Pandas as a last resort
    try:
        import pandas as pd

        ts = pd.to_datetime(text, errors="coerce", dayfirst=True)
        if ts is not pd.NaT:
            return ts.to_pydatetime()
    except Exception:  # noqa: BLE001
        pass

    return None


def _period_label(dt: datetime | None, fallback: str = "Unknown") -> str:
    return dt.strftime("%b %Y") if dt else fallback


# ---------------------------------------------------------------------------
# Per-period metric extraction
# ---------------------------------------------------------------------------

def _extract_period_metrics(parsed: dict, period_label: str) -> dict:
    """Pull the canonical metrics out of a single parsed settlement dict."""
    summary = parsed.get("summary", {}) or {}
    skus = parsed.get("skus", []) or []

    gross = float(summary.get("gross_sales_amount", 0) or 0)
    net = float(summary.get("net_bank_settlement", 0) or 0)
    total_orders = int(summary.get("total_sale_orders", 0) or 0)
    total_returns = int(summary.get("total_returns", 0) or 0)
    return_rate = round(total_returns / total_orders * 100, 2) if total_orders else 0.0
    mp_fees = float(summary.get("marketplace_fees", 0) or 0)
    mp_fee_pct = round(abs(mp_fees) / gross * 100, 2) if gross else 0.0
    ads = float(parsed.get("ads_total_spend", 0) or summary.get("ads_fees", 0) or 0)
    reclaimable = (
        float(summary.get("input_gst_tcs_credits", 0) or 0)
        + float(summary.get("income_tax_credits", 0) or 0)
        + abs(float(summary.get("tcs_amount", 0) or 0))
        + abs(float(summary.get("tds_amount", 0) or 0))
    )

    best = max(skus, key=lambda s: s.get("net_settlement", 0), default={})
    worst = min(skus, key=lambda s: s.get("net_settlement", 0), default={})

    return {
        "period": period_label,
        "gross_revenue": gross,
        "net_settlement": net,
        "return_rate": return_rate,
        "mp_fee_pct": mp_fee_pct,
        "mp_fees": mp_fees,
        "ads_spend": ads,
        "reclaimable_credits": reclaimable,
        "total_orders": total_orders,
        "total_returns": total_returns,
        "best_sku": best.get("seller_sku") or "—",
        "worst_sku": worst.get("seller_sku") or "—",
        "skus": skus,
    }


# ---------------------------------------------------------------------------
# Period normalisation & sort
# ---------------------------------------------------------------------------

def _normalise_periods(parsed_files: list[dict]) -> list[dict]:
    """Attach a sortable ``_dt`` and a human label to each parsed file."""
    out: list[dict] = []
    for idx, parsed in enumerate(parsed_files):
        summary = parsed.get("summary", {}) or {}
        dt = _parse_period(summary.get("payment_duration", ""))
        # Stable ordering when dt is missing — fall back to upload order
        sort_key = dt or datetime(1900, 1, 1 + idx % 28)
        label = _period_label(dt, fallback=f"Period {idx + 1}")
        metrics = _extract_period_metrics(parsed, label)
        metrics["_dt"] = sort_key
        out.append(metrics)

    out.sort(key=lambda m: m["_dt"])
    return out


# ---------------------------------------------------------------------------
# Period-over-period comparison
# ---------------------------------------------------------------------------

_TREND_FLAT_THRESHOLD = 1.5  # % change considered "flat"


def _trend(change_pct: float, *, lower_is_better: bool = False) -> str:
    """Return 'up' / 'down' / 'flat' based on change percentage."""
    if abs(change_pct) < _TREND_FLAT_THRESHOLD:
        return "flat"
    if change_pct > 0:
        return "up" if not lower_is_better else "up-bad"
    return "down" if not lower_is_better else "down-good"


def _compare(current: float, previous: float, lower_is_better: bool = False) -> dict:
    change_abs = round(current - previous, 2)
    change_pct = round((change_abs / previous * 100), 2) if previous else 0.0
    return {
        "current": round(current, 2),
        "previous": round(previous, 2),
        "change_abs": change_abs,
        "change_pct": change_pct,
        "trend": _trend(change_pct, lower_is_better=lower_is_better),
    }


# Metric name → (display label, lower_is_better)
_COMPARABLE_METRICS = {
    "gross_revenue": ("Gross Revenue", False),
    "net_settlement": ("Net Settlement", False),
    "return_rate": ("Return Rate %", True),
    "mp_fee_pct": ("Marketplace Fee %", True),
    "ads_spend": ("Ads Spend", True),
    "reclaimable_credits": ("Reclaimable Credits", False),
}


def build_pop_comparison(periods: list[dict]) -> dict:
    """Build period-over-period comparison for the latest two periods."""
    if len(periods) < 2:
        return {}
    current, previous = periods[-1], periods[-2]
    out: dict[str, dict] = {}
    for key, (label, lower_better) in _COMPARABLE_METRICS.items():
        out[key] = {
            "label": label,
            **_compare(current[key], previous[key], lower_is_better=lower_better),
        }

    # SKU-level
    out["best_sku"] = {
        "current": current["best_sku"],
        "previous": previous["best_sku"],
        "changed": current["best_sku"] != previous["best_sku"],
    }
    out["worst_sku"] = {
        "current": current["worst_sku"],
        "previous": previous["worst_sku"],
        "changed": current["worst_sku"] != previous["worst_sku"],
    }
    return out


# ---------------------------------------------------------------------------
# SKU trend tracking across all periods
# ---------------------------------------------------------------------------

def build_sku_trends(periods: list[dict]) -> list[dict]:
    """For every SKU appearing in 2+ periods, build a per-period trend record."""
    sku_history: dict[str, list[dict]] = {}
    for p in periods:
        for sku in p.get("skus", []):
            sid = sku.get("seller_sku")
            if not sid:
                continue
            sku_history.setdefault(sid, []).append({
                "period": p["period"],
                "revenue": float(sku.get("total_revenue", 0) or 0),
                "net_settlement": float(sku.get("net_settlement", 0) or 0),
                "return_rate": float(sku.get("return_rate", 0) or 0),
                "units_sold": int(sku.get("units_sold", 0) or 0),
            })

    results: list[dict] = []
    for sid, history in sku_history.items():
        if len(history) < 2:
            continue
        revenues = [h["revenue"] for h in history]
        returns = [h["return_rate"] for h in history]

        revenue_trend = _classify_trend(revenues, lower_is_better=False)
        return_trend = _classify_trend(returns, lower_is_better=True)

        gross_total = sum(revenues)
        net_total = sum(h["net_settlement"] for h in history)
        efficiency = round(net_total / gross_total * 100, 2) if gross_total else 0.0

        # Declining for 2+ consecutive months
        declining_streak = _consecutive_declines(revenues)
        flag_decline = declining_streak >= 2

        results.append({
            "seller_sku": sid,
            "history": history,
            "revenue_trend": revenue_trend,
            "return_rate_trend": return_trend,
            "settlement_efficiency_pct": efficiency,
            "consecutive_decline_months": declining_streak,
            "flag_declining": flag_decline,
        })

    # Surface the most concerning SKUs first
    results.sort(
        key=lambda r: (not r["flag_declining"], -r["consecutive_decline_months"]),
    )
    return results


def _classify_trend(values: list[float], *, lower_is_better: bool) -> str:
    """Return 'growing' / 'declining' / 'stable' based on first-vs-last value."""
    if len(values) < 2 or not values[0]:
        return "stable"
    pct = (values[-1] - values[0]) / abs(values[0]) * 100
    if abs(pct) < _TREND_FLAT_THRESHOLD:
        return "stable"
    if pct > 0:
        return "worsening" if lower_is_better else "growing"
    return "improving" if lower_is_better else "declining"


def _consecutive_declines(values: list[float]) -> int:
    """Count consecutive declines ending at the latest period."""
    streak = 0
    for i in range(len(values) - 1, 0, -1):
        if values[i] < values[i - 1]:
            streak += 1
        else:
            break
    return streak


# ---------------------------------------------------------------------------
# AI trend analysis
# ---------------------------------------------------------------------------

_TREND_SYSTEM_PROMPT = (
    "You are SellerLens AI, a financial analyst for Indian e-commerce sellers. "
    "Use INR (₹) and Indian numbering. Reference exact numbers from the data. "
    "Respond with valid JSON only."
)


def _build_period_table(periods: list[dict]) -> str:
    header = f"{'Period':<12} {'Gross':>14} {'Net':>14} {'Ret%':>7} {'MPFee%':>8} {'Ads':>12}"
    rows = [header, "-" * len(header)]
    for p in periods:
        rows.append(
            f"{p['period']:<12} "
            f"{_format_inr(p['gross_revenue']):>14} "
            f"{_format_inr(p['net_settlement']):>14} "
            f"{p['return_rate']:>6.1f}% "
            f"{p['mp_fee_pct']:>7.1f}% "
            f"{_format_inr(p['ads_spend']):>12}"
        )
    return "\n".join(rows)


def _ai_trend_analysis(periods: list[dict]) -> dict:
    """Call GPT-4o for a trend narrative. Falls back to rule-based on failure."""
    user_prompt = f"""Analyze this seller's performance trend across {len(periods)} months:

{_build_period_table(periods)}

Best SKU per period: {[p['best_sku'] for p in periods]}
Worst SKU per period: {[p['worst_sku'] for p in periods]}

Return strict JSON:
{{
  "growing_or_declining": "growing|declining|flat — with one-line evidence",
  "most_improved_metric": "metric name — exact change",
  "needs_urgent_attention": "metric name — exact problem",
  "next_month_prediction": "specific prediction with a number",
  "biggest_impact_action": "one concrete action this month"
}}"""

    try:
        client = _build_client()
        content, meta = _chat_with_retry(
            client,
            messages=[
                {"role": "system", "content": _TREND_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=900,
        )
        parsed = _safe_json_loads(content)
        parsed["_meta"] = meta
        return parsed
    except Exception as exc:  # noqa: BLE001
        logger.error("Trend analysis failed, using rule-based fallback: %s", exc)
        fallback = _rule_based_trend_analysis(periods)
        fallback["_meta"] = {"fallback": True, "error": str(exc)}
        return fallback


def _rule_based_trend_analysis(periods: list[dict]) -> dict:
    """Deterministic narrative when the API is unavailable."""
    first, last = periods[0], periods[-1]
    rev_change = (last["gross_revenue"] - first["gross_revenue"]) / first["gross_revenue"] * 100 if first["gross_revenue"] else 0
    net_change = (last["net_settlement"] - first["net_settlement"]) / first["net_settlement"] * 100 if first["net_settlement"] else 0

    direction = "growing" if rev_change > 5 else ("declining" if rev_change < -5 else "flat")

    # Most improved (largest positive change among "higher is better" metrics)
    candidates = []
    for key, (label, lower_better) in _COMPARABLE_METRICS.items():
        if not first[key]:
            continue
        pct = (last[key] - first[key]) / abs(first[key]) * 100
        score = -pct if lower_better else pct
        candidates.append((score, label, pct, lower_better))

    candidates.sort(reverse=True)
    most_improved_label, most_improved_pct = (candidates[0][1], candidates[0][2]) if candidates else ("Revenue", rev_change)
    needs_attention_label, needs_attention_pct = (candidates[-1][1], candidates[-1][2]) if candidates else ("Returns", 0)

    # Naive next-month prediction: linear projection of revenue
    if len(periods) >= 2:
        recent_growth = (last["gross_revenue"] - periods[-2]["gross_revenue"])
        next_predicted = last["gross_revenue"] + recent_growth
    else:
        next_predicted = last["gross_revenue"]

    return {
        "growing_or_declining": (
            f"{direction} — gross revenue moved {rev_change:+.1f}% from {first['period']} "
            f"({_format_inr(first['gross_revenue'])}) to {last['period']} "
            f"({_format_inr(last['gross_revenue'])})."
        ),
        "most_improved_metric": f"{most_improved_label} ({most_improved_pct:+.1f}%)",
        "needs_urgent_attention": f"{needs_attention_label} ({needs_attention_pct:+.1f}%)",
        "next_month_prediction": (
            f"Next month gross revenue likely around {_format_inr(next_predicted)} "
            f"based on recent trajectory (net settlement change {net_change:+.1f}%)."
        ),
        "biggest_impact_action": (
            "Focus on the SKUs flagged as declining for 2+ months — "
            "renegotiate cost price or pause ads on them this week."
        ),
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def analyze_multi_period(parsed_files: list[dict]) -> dict:
    """Run the full multi-period analysis.

    Args:
        parsed_files: list of canonical settlement dicts (from settlement_parser).

    Returns:
        Dashboard-ready dict (see module docstring for shape).
    """
    if not parsed_files:
        return {"error": "No periods supplied"}
    if len(parsed_files) > 6:
        parsed_files = parsed_files[:6]

    periods = _normalise_periods(parsed_files)
    period_labels = [p["period"] for p in periods]

    # Build the metric time series for charting
    metrics_series = {
        "revenue": [p["gross_revenue"] for p in periods],
        "net_settlement": [p["net_settlement"] for p in periods],
        "return_rate": [p["return_rate"] for p in periods],
        "mp_fee_pct": [p["mp_fee_pct"] for p in periods],
        "ads_spend": [p["ads_spend"] for p in periods],
        "reclaimable_credits": [p["reclaimable_credits"] for p in periods],
    }

    pop = build_pop_comparison(periods) if len(periods) >= 2 else {}
    sku_trends = build_sku_trends(periods)
    ai_analysis = _ai_trend_analysis(periods) if len(periods) >= 2 else {}

    # Best / worst month by net settlement
    best_month = max(periods, key=lambda p: p["net_settlement"])["period"]
    worst_month = min(periods, key=lambda p: p["net_settlement"])["period"]

    return {
        "periods": period_labels,
        "metrics": metrics_series,
        "pop_comparison": pop,
        "sku_trends": sku_trends,
        "ai_trend_analysis": ai_analysis,
        "best_month": best_month,
        "worst_month": worst_month,
        "period_count": len(periods),
    }
