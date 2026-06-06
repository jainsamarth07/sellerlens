"""Ads-report ingestion + analytics service (Flipkart campaign-level data).

Strictly additive — no other module is modified. Two storage scopes:

  * ``ad_campaigns`` table: one row per (user, campaign_id, period)
  * AI category-mapping cache (in-process; survives until restart)

All public helpers take an explicit ``user_id`` and never trust any value
sent from the frontend; this matches the security contract enforced by
the existing auth layer.
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.database import Base, engine
from backend.models.ads import AdCampaign

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Exact Flipkart ads-report columns we consume (after skipping the two header rows).
ADS_COLUMNS = {
    "campaign_id": "Campaign ID",
    "campaign_name": "Campaign Name",
    "campaign_status": "Campaign Status",
    "budget_type": "Budgeting Type",
    "campaign_budget": "Campaign Budget",
    "ad_spend": "Ad Spend",
    "views": "Views",
    "clicks": "SUM(clicks)",
    "conversions": "Total converted units",
    "revenue": "Total Revenue (Rs.)",
    "roi": "ROI",
    "ctr": "Click Through Rate",
    "conversion_rate": "Conversion Rate",
}

# Allowed product categories for the AI mapper.
CATEGORY_OPTIONS = [
    "stylus", "bag", "data_cable", "keyboard_skin", "mousepad", "otg_adapter",
    "laptop_stand", "travel_organizer", "electric_door_bell", "cases_covers",
    "mobile_holder", "usb_hub", "cleaning_kit", "laptop_sleeve", "headphone_case",
    "storage_box", "charger", "hdmi_cable", "aux_cable", "screwdriver_set",
    "shoe_organizer", "cloth_rack", "shower_filter", "monitor_arm", "ring_light",
    "tablet_stand", "desk_mat", "other",
]


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_ensured: set[int] = set()


def ensure_ads_table(target_engine: Engine | None = None) -> None:
    """Create the ``ad_campaigns`` table on first use (idempotent)."""
    eng = target_engine or engine
    key = id(eng)
    if key in _ensured:
        return
    Base.metadata.create_all(bind=eng, tables=[AdCampaign.__table__], checkfirst=True)
    _ensured.add(key)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_str(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def parse_ads_file(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Parse a Flipkart ads report and return one dict per campaign row.

    Accepts both ``.xlsx`` and ``.csv``. The Flipkart export has two
    metadata rows on top, so we skip them. Rows with ``Ad Spend == 0`` are
    excluded — they're historical campaigns with no activity.
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), skiprows=2, encoding="latin1")
    else:
        # .xlsx — Flipkart sheets are named per month, just take the first.
        xl = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
        df = xl.parse(xl.sheet_names[0], header=2)

    if df.empty:
        return []

    df.columns = [str(c).strip() for c in df.columns]
    required = ADS_COLUMNS["ad_spend"]
    if required not in df.columns:
        raise ValueError(f"Ads file is missing the required column: '{required}'.")

    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        spend = _to_float(row.get(ADS_COLUMNS["ad_spend"]))
        if spend <= 0:
            continue
        out.append(
            {
                "campaign_id": _to_str(row.get(ADS_COLUMNS["campaign_id"])),
                "campaign_name": _to_str(row.get(ADS_COLUMNS["campaign_name"])),
                "campaign_status": _to_str(row.get(ADS_COLUMNS["campaign_status"])),
                "budget_type": _to_str(row.get(ADS_COLUMNS["budget_type"])),
                "campaign_budget": _to_float(row.get(ADS_COLUMNS["campaign_budget"])),
                "ad_spend": spend,
                "views": _to_int(row.get(ADS_COLUMNS["views"])),
                "clicks": _to_int(row.get(ADS_COLUMNS["clicks"])),
                "conversions": _to_float(row.get(ADS_COLUMNS["conversions"])),
                "revenue": _to_float(row.get(ADS_COLUMNS["revenue"])),
                "roi": _to_float(row.get(ADS_COLUMNS["roi"])),
                "ctr": _to_float(row.get(ADS_COLUMNS["ctr"])),
                "conversion_rate": _to_float(row.get(ADS_COLUMNS["conversion_rate"])),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Persistence (per user + period — replaces existing rows for that period)
# ---------------------------------------------------------------------------

def save_campaigns(
    db: Session,
    *,
    user_id: int,
    rows: list[dict[str, Any]],
    settlement_period: str | None = None,
) -> int:
    """Replace this user's campaigns for *settlement_period* with *rows*.

    Returns the number of rows written.
    """
    ensure_ads_table(db.get_bind())

    # Delete existing rows for this (user, period) so re-uploads stay clean.
    db.execute(
        delete(AdCampaign).where(
            AdCampaign.user_id == user_id,
            AdCampaign.settlement_period == settlement_period,
        )
    )

    for r in rows:
        db.add(
            AdCampaign(
                user_id=user_id,
                settlement_period=settlement_period,
                campaign_id=r.get("campaign_id"),
                campaign_name=r.get("campaign_name"),
                campaign_status=r.get("campaign_status"),
                budget_type=r.get("budget_type"),
                campaign_budget=r.get("campaign_budget"),
                ad_spend=r.get("ad_spend") or 0,
                views=r.get("views"),
                clicks=r.get("clicks"),
                conversions=r.get("conversions"),
                revenue=r.get("revenue"),
                roi=r.get("roi"),
                ctr=r.get("ctr"),
                conversion_rate=r.get("conversion_rate"),
            )
        )
    db.commit()
    return len(rows)


def fetch_campaigns(
    db: Session,
    *,
    user_id: int,
    settlement_period: str | None = None,
) -> list[AdCampaign]:
    ensure_ads_table(db.get_bind())
    stmt = select(AdCampaign).where(AdCampaign.user_id == user_id)
    if settlement_period:
        stmt = stmt.where(AdCampaign.settlement_period == settlement_period)
    stmt = stmt.order_by(AdCampaign.ad_spend.desc())
    return list(db.execute(stmt).scalars())


def has_campaigns(db: Session, *, user_id: int) -> bool:
    ensure_ads_table(db.get_bind())
    return (
        db.execute(select(AdCampaign.id).where(AdCampaign.user_id == user_id).limit(1))
        .first()
        is not None
    )


# ---------------------------------------------------------------------------
# AI category mapping
# ---------------------------------------------------------------------------

_CATEGORY_PROMPT = """You are mapping Flipkart ad campaign names to product categories.

Settlement report categories available:
{categories}

Map each campaign name to one category from the list above.
If unclear, use 'other'.

Campaign names to map:
{names}

Return JSON only: {{ "campaign_name": "category", ... }}
"""


def map_categories(campaign_names: list[str]) -> dict[str, str]:
    """Call Azure OpenAI to map each campaign name to a category.

    Falls back to ``'other'`` for every campaign if the LLM is unavailable.
    """
    unique = sorted({n for n in campaign_names if n})
    if not unique:
        return {}

    try:
        from backend.services.azure_openai_service import (  # local import — optional dep
            _build_client,
            _chat_with_retry,
        )

        client = _build_client()
        prompt = _CATEGORY_PROMPT.format(
            categories=", ".join(CATEGORY_OPTIONS),
            names="\n".join(f"- {n}" for n in unique),
        )
        content, _meta = _chat_with_retry(
            client,
            messages=[
                {"role": "system", "content": "You are a precise classifier. Reply only with JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=2000,
        )
        data = json.loads(content)
        mapped = {
            str(k): (str(v).lower().strip() if v else "other")
            for k, v in data.items()
            if isinstance(k, str)
        }
        # Normalise unknown categories down to 'other'
        valid = set(CATEGORY_OPTIONS)
        return {k: (v if v in valid else "other") for k, v in mapped.items()}
    except Exception as exc:  # noqa: BLE001 — graceful fallback
        logger.warning("AI category mapping failed (%s) — defaulting to 'other'.", exc)
        return {n: "other" for n in unique}


def apply_category_mapping(
    db: Session, *, user_id: int, settlement_period: str | None = None
) -> int:
    """Run the AI mapper for the user's most recently uploaded campaigns.

    Returns the count of campaigns whose ``mapped_category`` was updated.
    """
    campaigns = fetch_campaigns(db, user_id=user_id, settlement_period=settlement_period)
    names = [c.campaign_name for c in campaigns if c.campaign_name]
    mapping = map_categories(names)
    updated = 0
    for c in campaigns:
        cat = mapping.get(c.campaign_name or "")
        if cat and cat != c.mapped_category:
            c.mapped_category = cat
            updated += 1
    if updated:
        db.commit()
    return updated


# ---------------------------------------------------------------------------
# Analysis (verdicts, summary, category cross-ref)
# ---------------------------------------------------------------------------

def verdict_for(roi: float | None, revenue: float | None) -> str:
    r = float(roi or 0)
    rev = float(revenue or 0)
    if rev <= 0 or r < 2:
        return "stop"
    if r < 4:
        return "watch"
    if r < 8:
        return "decent"
    return "star"


def _row_to_dict(c: AdCampaign) -> dict[str, Any]:
    spend = float(c.ad_spend or 0)
    rev = float(c.revenue or 0)
    roi = float(c.roi or 0)
    ctr = float(c.ctr or 0)
    cvr = float(c.conversion_rate or 0)
    return {
        "id": c.id,
        "campaign_id": c.campaign_id,
        "campaign_name": c.campaign_name,
        "status": c.campaign_status,
        "ad_spend": spend,
        "revenue": rev,
        "roi": round(roi, 4),
        "ctr_pct": round(ctr * 100, 4),
        "conversion_rate_pct": round(cvr * 100, 4),
        "verdict": verdict_for(roi, rev),
        "views": c.views or 0,
        "clicks": c.clicks or 0,
        "conversions": float(c.conversions or 0),
        "mapped_category": c.mapped_category,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "total_spend": 0.0,
            "total_revenue": 0.0,
            "overall_roi": 0.0,
            "wasted_spend": 0.0,
            "wasted_campaigns": 0,
            "underperforming_spend": 0.0,
            "campaigns_to_stop": [],
            "best_campaign": None,
            "worst_campaign": None,
            "total_campaigns": 0,
            "active_campaigns": 0,
        }

    total_spend = sum(r["ad_spend"] for r in rows)
    total_revenue = sum(r["revenue"] for r in rows)
    overall_roi = round(total_revenue / total_spend, 4) if total_spend else 0.0
    wasted = [r for r in rows if r["revenue"] <= 0]
    under = [r for r in rows if r["roi"] < 2]

    best = max(rows, key=lambda r: r["roi"])
    worst = min(rows, key=lambda r: r["roi"])

    return {
        "total_spend": round(total_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "overall_roi": overall_roi,
        "wasted_spend": round(sum(r["ad_spend"] for r in wasted), 2),
        "wasted_campaigns": len(wasted),
        "underperforming_spend": round(sum(r["ad_spend"] for r in under), 2),
        "campaigns_to_stop": [r["campaign_name"] for r in under if r["campaign_name"]],
        "best_campaign": {"name": best["campaign_name"], "roi": best["roi"]},
        "worst_campaign": {"name": worst["campaign_name"], "roi": worst["roi"]},
        "total_campaigns": len(rows),
        "active_campaigns": sum(
            1 for r in rows if (r["status"] or "").upper() == "LIVE"
        ),
    }


def _category_cross_ref(
    rows: list[dict[str, Any]], settlement_skus: list[dict] | None
) -> list[dict[str, Any]]:
    """Aggregate ad spend by mapped category and join with SKU revenue.

    ``settlement_skus`` is the parsed SKU list from the seller's settlement
    upload. Each SKU dict may have a ``mapped_category`` field that the
    listing service assigned, or we fall back to a simple keyword match
    on the product name / category text.
    """
    spend_by_cat: dict[str, float] = {}
    for r in rows:
        cat = r.get("mapped_category") or "other"
        spend_by_cat[cat] = spend_by_cat.get(cat, 0.0) + r["ad_spend"]

    revenue_by_cat: dict[str, float] = {}
    for s in settlement_skus or []:
        cat_raw = (s.get("category") or s.get("mapped_category") or "").strip().lower()
        if not cat_raw:
            continue
        # Normalise — match against our allowed list when possible.
        cat = next(
            (c for c in CATEGORY_OPTIONS if c in cat_raw or cat_raw in c),
            cat_raw,
        )
        revenue_by_cat[cat] = revenue_by_cat.get(cat, 0.0) + float(
            s.get("total_revenue", 0) or 0
        )

    out: list[dict[str, Any]] = []
    for cat in sorted(set(spend_by_cat) | set(revenue_by_cat)):
        ad_spend = round(spend_by_cat.get(cat, 0.0), 2)
        revenue = round(revenue_by_cat.get(cat, 0.0), 2)
        if ad_spend == 0 and revenue == 0:
            continue
        ratio = round((ad_spend / revenue) * 100, 2) if revenue else None
        if ratio is None:
            verdict = "unclear"
        elif ratio < 10:
            verdict = "efficient"
        elif ratio > 20:
            verdict = "expensive"
        else:
            verdict = "unclear"
        out.append(
            {
                "category": cat,
                "ad_spend": ad_spend,
                "settlement_revenue": revenue,
                "ad_cost_ratio_pct": ratio,
                "verdict": verdict,
            }
        )
    out.sort(key=lambda r: r["ad_spend"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# AI insights
# ---------------------------------------------------------------------------

_ADS_SYSTEM_PROMPT = (
    "You are an ads analyst for Indian Flipkart sellers. "
    "Marketplace fees average 15–25%, so an ad ROI below 4x typically means "
    "the seller is losing money after all costs. Be specific. Name actual "
    "campaigns. Use ₹ and Indian number format."
)


def _format_inr_basic(value: float) -> str:
    try:
        return f"₹{int(round(value)):,}"
    except (TypeError, ValueError):
        return f"₹{value}"


def _build_ads_context(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    cross_ref: list[dict[str, Any]],
    settlement_period: str | None,
) -> str:
    top10 = sorted(rows, key=lambda r: r["ad_spend"], reverse=True)[:10]
    low_roi = [r for r in rows if r["roi"] < 2][:15]

    top_lines = "\n".join(
        f"- {r['campaign_name']}: spend {_format_inr_basic(r['ad_spend'])}, "
        f"revenue {_format_inr_basic(r['revenue'])}, ROI {r['roi']:.2f}x"
        for r in top10
    ) or "(none)"

    low_lines = "\n".join(
        f"- {r['campaign_name']}: spent {_format_inr_basic(r['ad_spend'])} "
        f"for {_format_inr_basic(r['revenue'])} (ROI {r['roi']:.2f}x)"
        for r in low_roi
    ) or "(none)"

    cat_lines = "\n".join(
        f"- {c['category']}: ad {_format_inr_basic(c['ad_spend'])} / "
        f"revenue {_format_inr_basic(c['settlement_revenue'])} "
        f"= {c['ad_cost_ratio_pct']}% ({c['verdict']})"
        for c in cross_ref[:10]
    ) or "(no category mapping available yet)"

    period = settlement_period or "this period"
    return f"""Seller's {period} Flipkart Ads Performance:

Total Ad Spend: {_format_inr_basic(summary['total_spend'])}
Total Ad Revenue: {_format_inr_basic(summary['total_revenue'])}
Overall ROI: {summary['overall_roi']}x

Wasted spend (0 conversions): {_format_inr_basic(summary['wasted_spend'])} across {summary['wasted_campaigns']} campaigns

TOP CAMPAIGNS BY SPEND:
{top_lines}

CAMPAIGNS WITH ROI < 2 (losing money after marketplace fees):
{low_lines}

CATEGORY AD COST RATIOS:
{cat_lines}
"""


def _rule_based_ads_insights(
    rows: list[dict[str, Any]], summary: dict[str, Any]
) -> dict[str, Any]:
    """Cheap deterministic fallback when Azure OpenAI is unavailable."""
    insights: list[dict[str, Any]] = []

    stop_cands = sorted(
        [r for r in rows if r["roi"] < 2], key=lambda r: r["ad_spend"], reverse=True
    )[:3]
    if stop_cands:
        names = ", ".join(c["campaign_name"] for c in stop_cands)
        total = sum(c["ad_spend"] for c in stop_cands)
        insights.append(
            {
                "type": "stop",
                "title": "Pause loss-making campaigns",
                "finding": f"{len(stop_cands)} campaigns have ROI below 2x: {names}.",
                "action": "Pause these campaigns this week and redirect budget elsewhere.",
                "monthly_impact": f"Save ~{_format_inr_basic(total)}/month",
            }
        )

    scale_cands = sorted(
        [r for r in rows if r["roi"] >= 8], key=lambda r: r["revenue"], reverse=True
    )[:2]
    if scale_cands:
        names = ", ".join(c["campaign_name"] for c in scale_cands)
        insights.append(
            {
                "type": "scale",
                "title": "Scale your winners",
                "finding": f"Top ROI campaigns: {names} (ROI {scale_cands[0]['roi']:.1f}x).",
                "action": "Increase budget by 25-50% on these campaigns.",
                "monthly_impact": "Gain ~10-30% more revenue",
            }
        )

    opt_cands = [r for r in rows if 2 <= r["roi"] < 4]
    if opt_cands:
        insights.append(
            {
                "type": "optimize",
                "title": "Optimise watch-list campaigns",
                "finding": f"{len(opt_cands)} campaigns sit between 2x and 4x ROI — borderline after fees.",
                "action": "Tighten targeting keywords or cut budget by 25%.",
                "monthly_impact": "Recover ~10-15% of underperforming spend",
            }
        )

    insights.append(
        {
            "type": "info",
            "title": "Overall ads health",
            "finding": (
                f"You spent {_format_inr_basic(summary['total_spend'])} and earned "
                f"{_format_inr_basic(summary['total_revenue'])} (ROI {summary['overall_roi']}x)."
            ),
            "action": "Review the campaign table weekly and pause the worst 20%.",
            "monthly_impact": "Improve net ROI by 1-2x",
        }
    )
    return {"insights": insights[:4]}


def generate_ads_insights(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    cross_ref: list[dict[str, Any]],
    settlement_period: str | None = None,
) -> dict[str, Any]:
    """Call Azure OpenAI for 4 ads insights; fall back to rule-based if needed."""
    if not rows:
        return {"insights": []}

    context = _build_ads_context(rows, summary, cross_ref, settlement_period)
    user_prompt = (
        context
        + "\n\nReturn JSON with this exact shape:\n"
        + '{ "insights": [{"type": "stop|scale|optimize|info", '
          '"title": "max 8 words", "finding": "...", "action": "...", '
          '"monthly_impact": "..."}] }\n'
          "Generate exactly 4 insights."
    )

    try:
        from backend.services.azure_openai_service import (
            _build_client,
            _chat_with_retry,
        )

        client = _build_client()
        content, _meta = _chat_with_retry(
            client,
            messages=[
                {"role": "system", "content": _ADS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=1200,
        )
        parsed = json.loads(content)
        insights = parsed.get("insights") or []
        if not insights:
            return _rule_based_ads_insights(rows, summary)
        return {"insights": insights[:4]}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ads AI insights failed (%s) — using rule-based fallback.", exc)
        return _rule_based_ads_insights(rows, summary)


# ---------------------------------------------------------------------------
# Top-level orchestration (used by the API + chat context)
# ---------------------------------------------------------------------------

def build_analysis(
    db: Session,
    *,
    user_id: int,
    settlement_period: str | None = None,
    settlement_skus: list[dict] | None = None,
    include_insights: bool = True,
) -> dict[str, Any]:
    """Return the full ads-analysis payload for the API."""
    raw = fetch_campaigns(db, user_id=user_id, settlement_period=settlement_period)
    rows = [_row_to_dict(c) for c in raw]
    summary = _summary(rows)
    cross_ref = _category_cross_ref(rows, settlement_skus)
    insights: dict[str, Any] | None = None
    if include_insights:
        insights = generate_ads_insights(rows, summary, cross_ref, settlement_period)

    return {
        "settlement_period": settlement_period,
        "campaigns": rows,
        "summary": summary,
        "category_cross_reference": cross_ref,
        "ai_insights": insights,
    }


# ---------------------------------------------------------------------------
# Chat-context helper (consumed by chat_service when ads data is available)
# ---------------------------------------------------------------------------

def _build_product_context(
    rows: list[dict[str, Any]], settlement_skus: list[dict]
) -> str:
    """Build a product-level ad attribution context block.

    Attributes campaign spend proportionally to each SKU within its matched
    category, then computes true_profit and true_margin_pct.
    Returns an empty string if there is nothing useful to report.
    """
    if not rows or not settlement_skus:
        return ""

    # Build category spend and gross-revenue maps from campaigns + SKUs
    spend_by_cat: dict[str, float] = {}
    for r in rows:
        cat = (r.get("mapped_category") or "other").lower()
        spend_by_cat[cat] = spend_by_cat.get(cat, 0.0) + r["ad_spend"]

    gross_by_cat: dict[str, float] = {}
    net_by_cat: dict[str, float] = {}
    for s in settlement_skus:
        cat_raw = (s.get("category") or "").strip().lower()
        if not cat_raw:
            continue
        cat = next(
            (c for c in CATEGORY_OPTIONS if c in cat_raw or cat_raw in c),
            cat_raw,
        )
        gross_by_cat[cat] = gross_by_cat.get(cat, 0.0) + float(s.get("total_revenue", 0) or 0)
        net_by_cat[cat] = net_by_cat.get(cat, 0.0) + float(s.get("net_settlement", 0) or 0)

    # Per-SKU attribution
    sku_results: list[dict[str, Any]] = []
    for s in settlement_skus:
        gross_rev = float(s.get("total_revenue", 0) or 0)
        if gross_rev <= 0:
            continue
        cat_raw = (s.get("category") or "").strip().lower()
        matched_cat = next(
            (c for c in CATEGORY_OPTIONS if c in cat_raw or cat_raw in c),
            cat_raw or "other",
        )
        cat_gross = gross_by_cat.get(matched_cat, 0.0)
        cat_spend = spend_by_cat.get(matched_cat, 0.0)
        share = gross_rev / cat_gross if cat_gross > 0 else 0.0
        attributed_spend = cat_spend * share
        net_settlement = float(s.get("net_settlement", 0) or 0)
        true_profit = net_settlement - attributed_spend
        true_margin = (true_profit / gross_rev * 100) if gross_rev else 0
        ad_cost_pct = (attributed_spend / gross_rev * 100) if gross_rev else 0
        sku_results.append(
            {
                "sku": s.get("seller_sku", ""),
                "name": (s.get("product_name") or s.get("seller_sku") or "").strip(),
                "category": matched_cat,
                "gross_rev": gross_rev,
                "attributed_spend": attributed_spend,
                "true_profit": true_profit,
                "true_margin": true_margin,
                "ad_cost_pct": ad_cost_pct,
            }
        )

    if not sku_results:
        return ""

    loss_makers = sorted(
        [r for r in sku_results if r["true_profit"] < 0],
        key=lambda r: r["true_profit"],
    )[:5]
    best_performers = sorted(
        [r for r in sku_results if r["true_margin"] > 30],
        key=lambda r: r["true_margin"],
        reverse=True,
    )[:3]
    high_ad_cost = sorted(
        [r for r in sku_results if r["ad_cost_pct"] > 25 and r["true_profit"] > 0],
        key=lambda r: r["ad_cost_pct"],
        reverse=True,
    )[:3]

    total_loss = sum(abs(r["true_profit"]) for r in loss_makers)
    total_skus = len(sku_results)
    loss_count = len([r for r in sku_results if r["true_profit"] < 0])
    high_ad_count = len([r for r in sku_results if r["ad_cost_pct"] > 25])

    lines = [
        "PRODUCT-LEVEL AD ANALYSIS (attributed proportionally by category):",
        f"- Total SKUs with ad attribution: {total_skus}",
        f"- Products in LOSS after ads: {loss_count} (total loss: {_format_inr_basic(total_loss)})",
        f"- Products with ad cost > 25%: {high_ad_count}",
    ]
    if loss_makers:
        lines.append("Products losing money after attributed ad spend:")
        for r in loss_makers:
            lines.append(
                f"  - {r['name']} ({r['sku']}): revenue {_format_inr_basic(r['gross_rev'])}, "
                f"ad spend {_format_inr_basic(r['attributed_spend'])}, "
                f"net loss {_format_inr_basic(abs(r['true_profit']))} "
                f"(ad cost {r['ad_cost_pct']:.1f}% of revenue)"
            )
    if best_performers:
        lines.append("Best products after ads:")
        for r in best_performers:
            lines.append(
                f"  - {r['name']} ({r['sku']}): {r['true_margin']:.1f}% true margin, "
                f"ad cost only {r['ad_cost_pct']:.1f}%"
            )
    if high_ad_cost:
        lines.append("High ad cost products still profitable (consider reducing budget):")
        for r in high_ad_cost:
            lines.append(
                f"  - {r['name']} ({r['sku']}): {r['ad_cost_pct']:.1f}% ad cost, "
                f"{r['true_margin']:.1f}% true margin"
            )
    return "\n".join(lines)


def build_chat_context_block(
    db: Session,
    *,
    user_id: int,
    settlement_period: str | None = None,
    settlement_skus: list[dict] | None = None,
) -> str | None:
    """Short, dense ads block to append to the chat system context.

    Returns ``None`` if the user has no ads data — chat continues unaffected.
    When ``settlement_skus`` is provided the block also includes product-level
    ad attribution so the AI can answer SKU-specific ad questions.
    """
    raw = fetch_campaigns(db, user_id=user_id, settlement_period=settlement_period)
    if not raw:
        return None

    rows = [_row_to_dict(c) for c in raw]
    s = _summary(rows)
    best = s.get("best_campaign") or {}
    worst_active = min(
        (r for r in rows if r["ad_spend"] > 0),
        key=lambda r: r["roi"],
        default=None,
    )
    period = settlement_period or "this period"

    lines = [
        f"ADS SUMMARY ({period}):",
        f"- Total Ad Spend: {_format_inr_basic(s['total_spend'])}",
        f"- Total Ad Revenue: {_format_inr_basic(s['total_revenue'])}",
        f"- Overall ROI: {s['overall_roi']}x",
        f"- Campaigns with 0 revenue: {s['wasted_campaigns']} "
        f"({_format_inr_basic(s['wasted_spend'])} wasted)",
    ]
    if best.get("name"):
        lines.append(f"- Top campaign: {best['name']} — ROI {best['roi']}x")
    if worst_active:
        lines.append(
            f"- Worst active campaign: {worst_active['campaign_name']} — "
            f"ROI {worst_active['roi']}x, spent {_format_inr_basic(worst_active['ad_spend'])}"
        )

    product_ctx = _build_product_context(rows, settlement_skus or [])
    if product_ctx:
        lines.append("")
        lines.append(product_ctx)

    return "\n".join(lines)
