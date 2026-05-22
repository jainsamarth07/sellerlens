"""Core AI analysis engine — Azure OpenAI (gpt-4o) powered insights.

This is the brain of the product. It takes parsed settlement data
(see ``backend.processors.settlement_parser``) and produces structured,
actionable insights for Indian Flipkart / Amazon sellers.

Key features:
- Retry with exponential backoff on rate-limit / transient errors
- Rule-based fallback so the product still works if the API is down
- Per-call cost / latency logging (token counts → ₹ estimate)
- All prompts return strict JSON (parsed before returning)
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

from openai import APIError, AzureOpenAI, RateLimitError

from backend.config import settings

logger = logging.getLogger("analytics.azure_openai")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Cost table (USD → INR, indicative). Update from your Azure pricing page.
# ---------------------------------------------------------------------------
# gpt-4o pricing (per 1K tokens) as of mid-2026 in USD
_COST_PER_1K_INPUT_USD = 0.005
_COST_PER_1K_OUTPUT_USD = 0.015
_USD_TO_INR = 84.0


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _build_client() -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
        api_key=os.getenv("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    )


# ---------------------------------------------------------------------------
# Indian-numbering helpers
# ---------------------------------------------------------------------------

def _format_inr(value: float) -> str:
    """Format a number in Indian style: 12,34,567.89."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "₹0"
    sign = "-" if n < 0 else ""
    n = abs(n)
    int_part, _, dec_part = f"{n:.2f}".partition(".")
    if len(int_part) <= 3:
        out = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        # Group rest by 2 digits from the right
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        out = ",".join(groups + [last3])
    return f"₹{sign}{out}.{dec_part}"


def _build_sku_summary(skus: list[dict], top_n: int = 5) -> str:
    """Render the top-N SKUs by revenue as a markdown-ish bullet list."""
    if not skus:
        return "No SKU data available."
    top = sorted(skus, key=lambda s: s.get("total_revenue", 0), reverse=True)[:top_n]
    lines = []
    for s in top:
        # Prefer the human-friendly product name from the listing file if present;
        # fall back to the raw SKU code so legacy callers still work.
        label = s.get("product_name") or s.get("seller_sku", "UNKNOWN")
        sku_code = s.get("seller_sku", "")
        suffix = f" ({sku_code})" if s.get("product_name") and sku_code else ""
        lines.append(
            f"- {label}{suffix}: "
            f"revenue {_format_inr(s.get('total_revenue', 0))}, "
            f"net {_format_inr(s.get('net_settlement', 0))}, "
            f"units {s.get('units_sold', 0)}, "
            f"return rate {s.get('return_rate', 0)}%"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def _chat_with_retry(
    client: AzureOpenAI,
    messages: list[dict],
    *,
    max_attempts: int = 3,
    response_format: dict | None = None,
    temperature: float = 0.3,
    max_tokens: int = 1500,
) -> tuple[str, dict]:
    """Call chat.completions with retry. Returns (content, usage_metadata)."""
    deployment = settings.azure_openai_deployment_name
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        start = time.time()
        try:
            kwargs: dict[str, Any] = {
                "model": deployment,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            usage = response.usage

            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
            cost_usd = (
                input_tokens / 1000 * _COST_PER_1K_INPUT_USD
                + output_tokens / 1000 * _COST_PER_1K_OUTPUT_USD
            )
            cost_inr = round(cost_usd * _USD_TO_INR, 4)
            latency_ms = int((time.time() - start) * 1000)

            meta = {
                "attempt": attempt,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_inr": cost_inr,
                "latency_ms": latency_ms,
            }
            logger.info(
                "azure_openai_call deployment=%s tokens_in=%d tokens_out=%d cost_inr=%.4f latency_ms=%d",
                deployment, input_tokens, output_tokens, cost_inr, latency_ms,
            )
            return content, meta

        except RateLimitError as exc:
            last_exc = exc
            backoff = 2**attempt
            logger.warning("Rate-limited (attempt %d/%d). Sleeping %ds.", attempt, max_attempts, backoff)
            time.sleep(backoff)
        except APIError as exc:
            last_exc = exc
            logger.warning("APIError (attempt %d/%d): %s", attempt, max_attempts, exc)
            time.sleep(1)

    raise RuntimeError(f"Azure OpenAI call failed after {max_attempts} attempts") from last_exc


def _safe_json_loads(text: str) -> dict:
    """Tolerant JSON parser — strips markdown fences if present."""
    s = text.strip()
    if s.startswith("```"):
        s = s.strip("`")
        # remove leading "json\n" if present
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
    return json.loads(s)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert financial analyst for Indian e-commerce sellers. "
    "You understand Flipkart and Amazon marketplace economics deeply. "
    "You speak in plain English, use INR (₹), Indian number format (lakhs/crores), "
    "and give specific, actionable advice. Never give generic advice. "
    "Always reference actual numbers from the data. "
    "Always respond with valid JSON only — no prose, no markdown fences."
)


# ---------------------------------------------------------------------------
# Public API: generate_seller_insights
# ---------------------------------------------------------------------------

def generate_seller_insights(settlement_data: dict) -> dict:
    """Generate structured insights for a seller's settlement data.

    Returns a dict with keys: insights, health_score, health_label,
    one_line_summary. Falls back to a rule-based summary if the API fails.
    """
    summary = settlement_data.get("summary", {}) or {}
    skus = settlement_data.get("skus", []) or []

    gross = summary.get("gross_sales_amount", 0) or 0
    net = summary.get("net_bank_settlement", 0) or 0
    total_returns = summary.get("total_returns", 0) or 0
    total_orders = summary.get("total_sale_orders", 0) or 0
    return_rate = round(total_returns / total_orders * 100, 2) if total_orders else 0
    returns_reversal = summary.get("returns_reversal", 0) or 0
    mp_fees = summary.get("marketplace_fees", 0) or 0
    ads_spend = settlement_data.get("ads_total_spend", 0) or summary.get("ads_fees", 0) or 0
    reclaimable = (
        (summary.get("input_gst_tcs_credits", 0) or 0)
        + (summary.get("income_tax_credits", 0) or 0)
    )

    user_prompt = f"""Analyze this seller's April 2026 settlement data and generate insights:

SUMMARY:
- Gross Sales: {_format_inr(gross)}
- Net Settlement: {_format_inr(net)}
- Total Returns: {total_returns} orders ({return_rate}% rate)
- Returns Cost: {_format_inr(returns_reversal)}
- Marketplace Fees: {_format_inr(mp_fees)}
- Ads Spend: {_format_inr(ads_spend)}
- Reclaimable GST/TCS Credits: {_format_inr(reclaimable)}

TOP SKUs BY REVENUE:
{_build_sku_summary(skus)}

Generate exactly 5 insights in this JSON format:
{{
  "insights": [
    {{
      "type": "warning|opportunity|info",
      "title": "max 8 words",
      "finding": "specific observation with exact numbers",
      "action": "one concrete thing to do this week",
      "rupee_impact": "estimated monthly impact in ₹"
    }}
  ],
  "health_score": 0-100,
  "health_label": "Healthy|Needs Attention|Critical",
  "one_line_summary": "single sentence for the seller"
}}

Focus on: return rate, fee efficiency, SKU concentration risk,
reclaimable credits, ad spend efficiency."""

    try:
        client = _build_client()
        content, meta = _chat_with_retry(
            client,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=1800,
        )
        parsed = _safe_json_loads(content)
        parsed["_meta"] = meta
        return parsed
    except Exception as exc:  # noqa: BLE001 — fallback path
        logger.error("AI insight generation failed, using rule-based fallback: %s", exc)
        fallback = _rule_based_insights(
            gross=gross,
            net=net,
            return_rate=return_rate,
            returns_reversal=returns_reversal,
            mp_fees=mp_fees,
            ads_spend=ads_spend,
            reclaimable=reclaimable,
            skus=skus,
        )
        fallback["_meta"] = {"fallback": True, "error": str(exc)}
        return fallback


# ---------------------------------------------------------------------------
# Public API: analyze_sku
# ---------------------------------------------------------------------------

def analyze_sku(sku_data: dict, ad_spend_for_sku: float = 0.0) -> dict:
    """Generate a per-SKU recommendation. Falls back to rule-based logic on failure."""
    user_prompt = f"""Analyze this single SKU's performance and return JSON only:

SKU: {sku_data.get('seller_sku')}
Total Revenue: {_format_inr(sku_data.get('total_revenue', 0))}
Net Settlement: {_format_inr(sku_data.get('net_settlement', 0))}
Units Sold: {sku_data.get('units_sold', 0)}
Total Orders: {sku_data.get('total_orders', 0)}
Return Orders: {sku_data.get('return_orders', 0)}
Return Rate: {sku_data.get('return_rate', 0)}%
Avg Selling Price: {_format_inr(sku_data.get('avg_selling_price', 0))}
Net Per Unit: {_format_inr(sku_data.get('net_per_unit', 0))}
Marketplace Fees: {_format_inr(sku_data.get('total_mp_fees', 0))}
Refunds: {_format_inr(sku_data.get('total_refunds', 0))}
Ad Spend on this SKU: {_format_inr(ad_spend_for_sku)}

Return strictly this JSON:
{{
  "verdict": "star|average|loss-maker",
  "return_rate_benchmark": "below average|on par|above average — with category context",
  "pricing_recommendation": "concrete pricing advice",
  "ad_spend_verdict": "worth it|stop|scale",
  "action_item": "one concrete thing to do this week"
}}"""

    try:
        client = _build_client()
        content, meta = _chat_with_retry(
            client,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=600,
        )
        parsed = _safe_json_loads(content)
        parsed["_meta"] = meta
        return parsed
    except Exception as exc:  # noqa: BLE001
        logger.error("SKU analysis failed for %s, using fallback: %s", sku_data.get("seller_sku"), exc)
        fallback = _rule_based_sku(sku_data, ad_spend_for_sku)
        fallback["_meta"] = {"fallback": True, "error": str(exc)}
        return fallback


# ---------------------------------------------------------------------------
# Rule-based fallbacks
# ---------------------------------------------------------------------------

def _rule_based_insights(
    *,
    gross: float,
    net: float,
    return_rate: float,
    returns_reversal: float,
    mp_fees: float,
    ads_spend: float,
    reclaimable: float,
    skus: list[dict],
) -> dict:
    """Deterministic fallback so the product still works if the API is down."""
    insights: list[dict] = []

    # 1. Return rate
    if return_rate > 10:
        insights.append({
            "type": "warning",
            "title": "High return rate hurting margins",
            "finding": f"Return rate is {return_rate}%, well above the 5-7% healthy band. Returns cost {_format_inr(returns_reversal)} this period.",
            "action": "Audit your top-3 highest-return SKUs and improve product images / sizing info this week.",
            "rupee_impact": _format_inr(abs(returns_reversal) * 0.4),
        })
    else:
        insights.append({
            "type": "info",
            "title": "Return rate within healthy range",
            "finding": f"Return rate of {return_rate}% is healthy.",
            "action": "Maintain current quality control.",
            "rupee_impact": _format_inr(0),
        })

    # 2. Fee efficiency
    fee_ratio = (abs(mp_fees) / gross * 100) if gross else 0
    if fee_ratio > 20:
        insights.append({
            "type": "warning",
            "title": "Marketplace fees consuming margin",
            "finding": f"Marketplace fees are {fee_ratio:.1f}% of gross sales ({_format_inr(mp_fees)}). Above 20% is concerning.",
            "action": "Review fee structure with your category manager and consider repricing top SKUs.",
            "rupee_impact": _format_inr(abs(mp_fees) * 0.1),
        })

    # 3. SKU concentration risk
    if skus:
        top_revenue = max(s.get("total_revenue", 0) for s in skus)
        if gross and top_revenue / gross > 0.4:
            insights.append({
                "type": "warning",
                "title": "Revenue concentrated in one SKU",
                "finding": f"Top SKU contributes {top_revenue / gross * 100:.1f}% of revenue. High concentration risk.",
                "action": "Launch 2-3 complementary SKUs to diversify within 30 days.",
                "rupee_impact": _format_inr(top_revenue * 0.2),
            })

    # 4. Reclaimable credits
    if reclaimable > 0:
        insights.append({
            "type": "opportunity",
            "title": "Unclaimed GST/TCS credits available",
            "finding": f"You have {_format_inr(reclaimable)} in reclaimable GST/TCS/TDS credits.",
            "action": "File this period's GSTR-3B and Form 26AS reconciliation to recover these.",
            "rupee_impact": _format_inr(reclaimable),
        })

    # 5. Ad spend efficiency
    if ads_spend and gross:
        acos = ads_spend / gross * 100
        if acos > 15:
            insights.append({
                "type": "warning",
                "title": "Ad spend ratio is too high",
                "finding": f"Ad spend is {acos:.1f}% of gross sales ({_format_inr(ads_spend)}). Target ACoS is 8-12%.",
                "action": "Pause campaigns with ACoS > 25% and reallocate budget to top-performing SKUs.",
                "rupee_impact": _format_inr(ads_spend * 0.25),
            })
        else:
            insights.append({
                "type": "info",
                "title": "Ad spend efficient",
                "finding": f"ACoS of {acos:.1f}% is within healthy range.",
                "action": "Consider scaling top-performing campaigns by 20%.",
                "rupee_impact": _format_inr(gross * 0.05),
            })
    else:
        insights.append({
            "type": "opportunity",
            "title": "No ad spend detected",
            "finding": "You're not running marketplace ads this period.",
            "action": "Test sponsored ads on your top-3 SKUs with ₹500/day budget.",
            "rupee_impact": _format_inr(gross * 0.1),
        })

    # Pad to 5
    while len(insights) < 5:
        insights.append({
            "type": "info",
            "title": "Keep monitoring core metrics",
            "finding": f"Net settlement of {_format_inr(net)} on gross of {_format_inr(gross)}.",
            "action": "Review weekly settlement reports.",
            "rupee_impact": _format_inr(0),
        })

    # Health score: simple weighted heuristic (0-100)
    score = 100
    if return_rate > 10:
        score -= 20
    if fee_ratio > 20:
        score -= 15
    if gross and net / gross < 0.5:
        score -= 20
    score = max(0, min(100, score))
    label = "Healthy" if score >= 75 else ("Needs Attention" if score >= 50 else "Critical")

    return {
        "insights": insights[:5],
        "health_score": score,
        "health_label": label,
        "one_line_summary": (
            f"Net settlement of {_format_inr(net)} on gross sales of {_format_inr(gross)} — "
            f"status: {label.lower()}."
        ),
    }


def _rule_based_sku(sku: dict, ad_spend: float) -> dict:
    """Deterministic SKU verdict used when the API is unavailable."""
    net_per_unit = sku.get("net_per_unit", 0) or 0
    return_rate = sku.get("return_rate", 0) or 0
    revenue = sku.get("total_revenue", 0) or 0

    if net_per_unit < 0:
        verdict = "loss-maker"
    elif net_per_unit > 100 and return_rate < 8:
        verdict = "star"
    else:
        verdict = "average"

    if return_rate < 5:
        bench = "below average — better than typical 5-8% category benchmark"
    elif return_rate < 10:
        bench = "on par — within typical 5-10% category band"
    else:
        bench = "above average — exceeds 10% which is concerning"

    if net_per_unit < 0:
        pricing = f"Increase price by ₹{abs(net_per_unit) + 50:.0f} or discontinue."
    elif net_per_unit < 50:
        pricing = "Test a 5-10% price increase to improve unit economics."
    else:
        pricing = "Pricing is healthy — hold current price."

    if ad_spend == 0:
        ad_verdict = "scale" if verdict == "star" else "worth it"
    elif revenue and ad_spend / revenue > 0.2:
        ad_verdict = "stop"
    else:
        ad_verdict = "scale" if verdict == "star" else "worth it"

    action = {
        "star": "Increase ad budget by 25% and ensure inventory for next 60 days.",
        "average": "Run a 7-day price A/B test to find the optimum.",
        "loss-maker": "Pause ads on this SKU and renegotiate cost price with supplier.",
    }[verdict]

    return {
        "verdict": verdict,
        "return_rate_benchmark": bench,
        "pricing_recommendation": pricing,
        "ad_spend_verdict": ad_verdict,
        "action_item": action,
    }
