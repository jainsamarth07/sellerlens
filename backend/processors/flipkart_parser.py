"""Parser for Flipkart seller settlement Excel (.xlsx) reports.

Flipkart settlement workbooks contain these sheets:
    - "Summary of report"   : high-level totals, label/value layout
    - "Orders"              : multi-row header (row 0 = group, row 1 = column)
    - "Ads"                 : advertising spend rows
    - "GST_Details"         : tax breakdown
    - "TCS_Recovery"        : TCS deductions

The parser is intentionally tolerant of column-name drift between settlement
versions and of NaN / currency-formatted values.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from backend.processors._helpers import (
    clean_column_name,
    find_column,
    is_placeholder_value,
    normalise_label,
    safe_str,
    to_float,
    to_int,
)

# ---------------------------------------------------------------------------
# Sheet name resolution
# ---------------------------------------------------------------------------

_SHEET_ALIASES: dict[str, list[str]] = {
    "summary": ["summary of report", "summary", "report summary"],
    "orders": ["orders", "order details", "order"],
    "ads": ["ads", "advertising", "ad spend"],
    "gst": ["gst_details", "gst details", "gst"],
    "tcs": ["tcs_recovery", "tcs recovery", "tcs"],
}


def _resolve_sheet(xl: pd.ExcelFile, key: str) -> str | None:
    aliases = _SHEET_ALIASES.get(key, [key])
    norm_sheets = {normalise_label(s): s for s in xl.sheet_names}
    for alias in aliases:
        n = normalise_label(alias)
        if n in norm_sheets:
            return norm_sheets[n]
        for ns, original in norm_sheets.items():
            if n and n in ns:
                return original
    return None


# ---------------------------------------------------------------------------
# Summary sheet
# ---------------------------------------------------------------------------

# Map our canonical field → list of possible row labels in the workbook.
# Order matters: more specific aliases first.
_SUMMARY_LABEL_MAP: dict[str, list[str]] = {
    "payment_duration": ["payment duration", "settlement period", "period"],
    "total_sale_orders": [
        "sale orders not returned",
        "total sale orders",
        "total orders",
        "sale orders",
    ],
    "total_returns": ["total returns", "return orders", "returns"],
    "gross_sales_amount": ["sales amount", "gross sales amount", "gross sales"],
    "returns_reversal": ["returns reversal", "return amount"],
    "marketplace_fees": ["marketplace fees", "marketplace fee", "mp fees"],
    "tcs_amount": ["tcs amount", "tcs"],
    "tds_amount": ["tds amount", "tds"],
    "gst_on_mp_fees": [
        "gst on marketplace fees",
        "gst on mp fees",
        "gst on mp fee",
    ],
    "ads_fees": ["ads fees", "ads fee", "advertising fees"],
    "net_bank_settlement": [
        "net bank settlement a",
        "net bank settlement",
        "bank settlement",
        "net settlement",
    ],
    "input_gst_tcs_credits": [
        "input gst tcs credits b",
        "input gst tcs credits",
        "input gst credits",
        "gst credits",
    ],
    "income_tax_credits": [
        "income tax credits c",
        "income tax credits",
        "income tax credit",
    ],
    "total_realizable_amount": [
        "total realizable amount",
        "total realisable amount",
        "realizable amount",
    ],
}

_NUMERIC_SUMMARY_FIELDS = {
    "gross_sales_amount",
    "returns_reversal",
    "marketplace_fees",
    "tcs_amount",
    "tds_amount",
    "gst_on_mp_fees",
    "ads_fees",
    "net_bank_settlement",
    "input_gst_tcs_credits",
    "income_tax_credits",
    "total_realizable_amount",
}


def _row_label_value_pairs(row_cells: list[Any]) -> list[tuple[str, Any]]:
    """Return ``[(label, value), ...]`` pairs from one summary row.

    Handles both layouts:
      - ``[label, value, ...]`` (legacy pair-format)
      - ``[None, label, None, value, ...]`` (real Flipkart structured table)
    Strings starting with ``#gid=`` (Google-Sheets cross-references) are skipped.
    """
    # Index → cell, dropping NaN
    cells = [(i, c) for i, c in enumerate(row_cells) if pd.notna(c)]
    if len(cells) < 2:
        return []

    pairs: list[tuple[str, Any]] = []
    # Strategy: find the first textual cell (label) and pair it with the first
    # numeric cell to its right. If no numeric cell, pair with next textual cell
    # (covers payment_duration which has a date-string value).
    for li, (lcol, lval) in enumerate(cells):
        if not isinstance(lval, str):
            continue
        label = lval.strip()
        if not label or is_placeholder_value(label):
            continue
        # Look for the matching value to the right
        for vi in range(li + 1, len(cells)):
            vcol, vval = cells[vi]
            if is_placeholder_value(vval):
                continue
            # Prefer a numeric value; otherwise accept a short string (date / period)
            if isinstance(vval, (int, float)) or (
                isinstance(vval, str) and len(vval.strip()) <= 80 and not vval.strip().lower().startswith("this is")
            ):
                pairs.append((label, vval))
                break
        # Only the first label per row matters for our lookup
        break
    return pairs


def _build_summary_lookup(df: pd.DataFrame) -> dict[str, Any]:
    """Build a normalised label → value lookup from every row of the summary sheet."""
    lookup: dict[str, Any] = {}
    if df is None or df.empty:
        return lookup
    for _, row in df.iterrows():
        for label, value in _row_label_value_pairs(row.tolist()):
            key = normalise_label(label)
            if key and key not in lookup:
                lookup[key] = value
    return lookup


def parse_summary_sheet(df: pd.DataFrame) -> dict[str, Any]:
    """Extract canonical summary fields from the 'Summary of report' sheet.

    Robust to two layouts:
      1. Legacy: ``Field | Value`` pairs (used by our sample workbook)
      2. Real Flipkart: a structured table with ``Line Item | Break-up L1 |
         Break-up L2 | Amount Settled (Rs.) | …`` columns where many break-up
         values are unresolved Google-Sheets formulas (``#gid=…``).
    """
    lookup = _build_summary_lookup(df)
    summary: dict[str, Any] = {}

    for field, aliases in _SUMMARY_LABEL_MAP.items():
        raw_value: Any = None
        for alias in aliases:
            key = normalise_label(alias)
            if key in lookup:
                raw_value = lookup[key]
                break
            # partial / contains match (prefer shortest containing key)
            matches = [(k, v) for k, v in lookup.items() if key and key in k]
            if matches:
                matches.sort(key=lambda kv: len(kv[0]))
                raw_value = matches[0][1]
                break

        if field == "payment_duration":
            summary[field] = safe_str(raw_value)
        elif field in {"total_sale_orders", "total_returns"}:
            summary[field] = to_int(raw_value)
        else:
            summary[field] = to_float(raw_value)

    return summary


# ---------------------------------------------------------------------------
# Orders sheet
# ---------------------------------------------------------------------------

# Canonical field → candidate header names (post-normalisation handled in find_column)
_ORDER_FIELD_MAP: dict[str, list[str]] = {
    "order_id": ["order id", "order_id"],
    "order_item_id": ["order item id", "order_item_id", "item id"],
    "payment_date": ["payment date", "settlement date", "date"],
    "sale_amount": ["sale amount", "sales amount", "selling price"],
    "marketplace_fee": ["marketplace fee", "mp fee", "marketplace fees"],
    "taxes": ["taxes", "tax", "total taxes"],
    "refund_amount": ["refund amount", "refund", "return amount"],
    "bank_settlement_value": [
        "bank settlement value",
        "bank settlement",
        "settlement value",
    ],
    "seller_sku": ["seller sku id", "seller sku", "sku", "sku id"],
    "quantity": ["quantity", "qty", "units"],
    "product_sub_category": [
        "product sub category",
        "sub category",
        "product subcategory",
        "category",
    ],
    "return_type": ["return type", "type of return"],
    "commission": ["commission", "commission fee"],
    "fixed_fee": ["fixed fee", "fixed_fee"],
    "collection_fee": ["collection fee", "collection_fee"],
    "reverse_shipping_fee": [
        "reverse shipping fee",
        "reverse shipping",
        "return shipping fee",
    ],
    "tcs": ["tcs"],
    "tds": ["tds"],
    "gst_on_mp_fees": ["gst on mp fees", "gst on marketplace fees", "gst on mp fee"],
}

_ORDER_NUMERIC_FIELDS = {
    "sale_amount",
    "marketplace_fee",
    "taxes",
    "refund_amount",
    "bank_settlement_value",
    "commission",
    "fixed_fee",
    "collection_fee",
    "reverse_shipping_fee",
    "tcs",
    "tds",
    "gst_on_mp_fees",
}


def _flatten_multi_header(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten a MultiIndex header into single strings and clean Flipkart noise.

    - Picks the deepest non-"Unnamed" level for MultiIndex columns.
    - Strips "(Rs.)" suffixes and trailing formula annotations (anything after
      ``\\n``, ``=``, or ``[``) so callers can match on clean field names.
    - Disambiguates duplicate column names by appending ``__2``, ``__3`` etc.
    """
    if isinstance(df.columns, pd.MultiIndex):
        flattened = []
        for tup in df.columns:
            chosen = ""
            for part in reversed(tup):
                p = safe_str(part)
                if p and not p.lower().startswith("unnamed"):
                    chosen = p
                    break
            flattened.append(chosen)
        df.columns = flattened

    # Clean every column name (strip (Rs.) and trailing formulas)
    cleaned: list[str] = []
    for col in df.columns:
        c = clean_column_name(col)
        if not c:
            c = safe_str(col)
        cleaned.append(c)

    # Disambiguate duplicates so find_column reliably hits the first occurrence.
    seen: dict[str, int] = {}
    final: list[str] = []
    for c in cleaned:
        if c in seen:
            seen[c] += 1
            final.append(f"{c}__{seen[c]}")
        else:
            seen[c] = 1
            final.append(c)
    df.columns = final
    return df


def parse_orders_sheet(df: pd.DataFrame) -> tuple[list[dict], list[str]]:
    """Convert the Orders sheet into a list of normalised order dicts."""
    errors: list[str] = []
    if df is None or df.empty:
        return [], errors

    df = _flatten_multi_header(df.copy())

    # Resolve column name for each canonical field
    col_lookup: dict[str, str | None] = {
        field: find_column(df, *aliases) for field, aliases in _ORDER_FIELD_MAP.items()
    }

    missing = [k for k, v in col_lookup.items() if v is None and k in {"order_id", "sale_amount"}]
    if missing:
        errors.append(f"Orders sheet missing required columns: {', '.join(missing)}")

    orders: list[dict] = []
    for idx, row in df.iterrows():
        try:
            record: dict[str, Any] = {}
            for field, col in col_lookup.items():
                raw = row[col] if col is not None and col in row else None
                if field in _ORDER_NUMERIC_FIELDS:
                    record[field] = to_float(raw)
                elif field == "quantity":
                    record[field] = to_int(raw, default=1) or 1
                elif field == "payment_date":
                    record[field] = (
                        pd.to_datetime(raw, errors="coerce").isoformat()
                        if pd.notna(raw)
                        else None
                    )
                else:
                    record[field] = safe_str(raw) or None

            # Skip completely empty rows (no order_id and no sale_amount)
            if not record.get("order_id") and not record.get("sale_amount"):
                continue
            orders.append(record)
        except Exception as exc:  # noqa: BLE001 — per-row resilience
            errors.append(f"Orders row {idx}: {exc}")

    return orders, errors


# ---------------------------------------------------------------------------
# Ads sheet
# ---------------------------------------------------------------------------

_ADS_FIELD_MAP: dict[str, list[str]] = {
    "campaign_id": [
        "campaign transaction id",
        "campaign id",
        "campaign_id",
        "campaign",
        "transaction id",
    ],
    "transaction_type": ["transaction type", "type", "txn type"],
    "amount": ["amount", "spend", "ad spend", "settlement value"],
    "wallet_topup": ["wallet topup", "wallet top up", "topup"],
    "wallet_refund": ["wallet refund"],
    "wallet_redeem": ["wallet redeem"],
    "gst_on_ads": ["gst on ads fees", "gst on ads", "gst", "gst amount"],
}


def parse_ads_sheet(df: pd.DataFrame) -> tuple[list[dict], float, list[str]]:
    """Return per-row ad records, total ad spend, and any per-row errors.

    Real Flipkart Ads sheets use a wallet-based layout
    (``Wallet Topup`` − ``Wallet Refund``); legacy / sample sheets expose a
    single ``Amount`` column. Both are supported.
    """
    errors: list[str] = []
    if df is None or df.empty:
        return [], 0.0, errors

    df = _flatten_multi_header(df.copy())
    col_lookup = {f: find_column(df, *a) for f, a in _ADS_FIELD_MAP.items()}

    rows: list[dict] = []
    total_spend = 0.0

    has_wallet = bool(col_lookup["wallet_topup"] or col_lookup["wallet_refund"])
    has_amount = bool(col_lookup["amount"])

    for idx, row in df.iterrows():
        try:
            gst = abs(to_float(row[col_lookup["gst_on_ads"]])) if col_lookup["gst_on_ads"] else 0.0

            if has_wallet:
                topup = to_float(row[col_lookup["wallet_topup"]]) if col_lookup["wallet_topup"] else 0.0
                refund = to_float(row[col_lookup["wallet_refund"]]) if col_lookup["wallet_refund"] else 0.0
                # Net cash spent on ads this row
                amount = topup - refund
            elif has_amount:
                amount = to_float(row[col_lookup["amount"]])
            else:
                amount = 0.0

            campaign_id = (
                safe_str(row[col_lookup["campaign_id"]]) if col_lookup["campaign_id"] else ""
            )
            txn_type = (
                safe_str(row[col_lookup["transaction_type"]]) if col_lookup["transaction_type"] else ""
            )

            # Skip rows that have no identifying info AND no money movement
            if not campaign_id and not txn_type and amount == 0 and gst == 0:
                continue

            rows.append(
                {
                    "campaign_id": campaign_id,
                    "transaction_type": txn_type,
                    "amount": round(amount, 2),
                    "gst_on_ads": round(gst, 2),
                }
            )
            total_spend += amount + gst
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Ads row {idx}: {exc}")

    return rows, round(total_spend, 2), errors


# ---------------------------------------------------------------------------
# SKU aggregation
# ---------------------------------------------------------------------------

def aggregate_skus(orders: list[dict]) -> list[dict]:
    """Group orders by seller_sku and compute per-SKU profitability metrics."""
    if not orders:
        return []

    df = pd.DataFrame(orders)
    if "seller_sku" not in df.columns:
        return []

    df["seller_sku"] = df["seller_sku"].fillna("UNKNOWN")
    for col in [
        "sale_amount",
        "marketplace_fee",
        "refund_amount",
        "reverse_shipping_fee",
        "bank_settlement_value",
        "quantity",
    ]:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    grouped = df.groupby("seller_sku", dropna=False)

    results: list[dict] = []
    for sku, g in grouped:
        units_sold = int(g["quantity"].sum())
        total_orders = int(len(g))
        return_orders = int((g["refund_amount"] < 0).sum())
        total_revenue = float(g["sale_amount"].sum())
        total_mp_fees = float(g["marketplace_fee"].sum())
        total_refunds = float(g["refund_amount"].sum())
        total_reverse_shipping = float(g["reverse_shipping_fee"].sum())
        net_settlement = float(g["bank_settlement_value"].sum())

        avg_selling_price = total_revenue / units_sold if units_sold else 0.0
        net_per_unit = net_settlement / units_sold if units_sold else 0.0
        return_rate = (return_orders / total_orders * 100) if total_orders else 0.0

        results.append(
            {
                "seller_sku": str(sku),
                "total_revenue": round(total_revenue, 2),
                "total_mp_fees": round(total_mp_fees, 2),
                "total_refunds": round(total_refunds, 2),
                "total_reverse_shipping": round(total_reverse_shipping, 2),
                "net_settlement": round(net_settlement, 2),
                "units_sold": units_sold,
                "total_orders": total_orders,
                "return_orders": return_orders,
                "return_rate": round(return_rate, 2),
                "avg_selling_price": round(avg_selling_price, 2),
                "net_per_unit": round(net_per_unit, 2),
            }
        )

    results.sort(key=lambda r: r["net_settlement"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse_flipkart_settlement(file_bytes: bytes) -> dict[str, Any]:
    """Parse a Flipkart settlement .xlsx and return the canonical analytics dict."""
    parsing_errors: list[str] = []
    result: dict[str, Any] = {
        "platform": "flipkart",
        "summary": {},
        "orders": [],
        "ads_total_spend": 0.0,
        "ads": [],
        "skus": [],
        "parsing_errors": parsing_errors,
    }

    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception as exc:  # noqa: BLE001
        parsing_errors.append(f"Failed to open workbook: {exc}")
        return result

    # --- Summary -------------------------------------------------------------
    summary_sheet = _resolve_sheet(xl, "summary")
    if summary_sheet:
        try:
            summary_df = xl.parse(summary_sheet, header=None)
            result["summary"] = parse_summary_sheet(summary_df)
        except Exception as exc:  # noqa: BLE001
            parsing_errors.append(f"Summary sheet error: {exc}")
    else:
        parsing_errors.append("Summary sheet not found")

    # --- Orders --------------------------------------------------------------
    orders_sheet = _resolve_sheet(xl, "orders")
    if orders_sheet:
        try:
            # header=1 → second row contains column names (first row is the group)
            orders_df = xl.parse(orders_sheet, header=1)
            orders, errs = parse_orders_sheet(orders_df)
            result["orders"] = orders
            parsing_errors.extend(errs)
        except Exception as exc:  # noqa: BLE001
            parsing_errors.append(f"Orders sheet error: {exc}")
    else:
        parsing_errors.append("Orders sheet not found")

    # --- Ads -----------------------------------------------------------------
    ads_sheet = _resolve_sheet(xl, "ads")
    if ads_sheet:
        try:
            ads_df = _read_ads_sheet(xl, ads_sheet)
            ads_rows, total_spend, errs = parse_ads_sheet(ads_df)
            result["ads"] = ads_rows
            result["ads_total_spend"] = total_spend
            parsing_errors.extend(errs)
        except Exception as exc:  # noqa: BLE001
            parsing_errors.append(f"Ads sheet error: {exc}")

    # --- SKU aggregation -----------------------------------------------------
    result["skus"] = aggregate_skus(result["orders"])

    # --- Backfill missing summary fields from Orders aggregates --------------
    # Real Flipkart summary sheets store many break-up values as cross-sheet
    # formulas (#gid=…) that don't resolve when read by openpyxl. Recover the
    # numbers by aggregating the Orders rows we already parsed.
    _backfill_summary(result["summary"], result["orders"], result["ads_total_spend"])

    return result


_ADS_PROBE_COLUMNS = ("type", "transaction type", "amount", "wallet topup", "wallet refund", "campaign id")


def _read_ads_sheet(xl: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    """Read the Ads sheet, auto-detecting whether row 0 is a group header.

    Tries ``header=0`` first (legacy / sample layout). If no recognisable ads
    column is found, retries with ``header=1`` (real Flipkart layout).
    """
    df = xl.parse(sheet, header=0)
    if any(find_column(df, c) for c in _ADS_PROBE_COLUMNS):
        return df
    df1 = xl.parse(sheet, header=1)
    if any(find_column(df1, c) for c in _ADS_PROBE_COLUMNS):
        return df1
    return df


def _backfill_summary(summary: dict, orders: list[dict], ads_total_spend: float) -> None:
    """Fill summary fields that are zero/empty by aggregating Orders rows."""
    if not orders:
        return

    df = pd.DataFrame(orders)
    for col in (
        "sale_amount",
        "marketplace_fee",
        "refund_amount",
        "tcs",
        "tds",
        "gst_on_mp_fees",
        "taxes",
    ):
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    derived = {
        "gross_sales_amount": float(df["sale_amount"].sum()),
        "marketplace_fees": float(df["marketplace_fee"].sum()),
        # Refund column carries negative values for returned orders;
        # `returns_reversal` is conventionally a positive amount.
        "returns_reversal": float(-df["refund_amount"].clip(upper=0).sum()),
        "tcs_amount": float(df["tcs"].sum()),
        "tds_amount": float(df["tds"].sum()),
        "gst_on_mp_fees": float(df["gst_on_mp_fees"].sum()),
    }
    for field, value in derived.items():
        if not summary.get(field):
            summary[field] = round(value, 2)

    if not summary.get("ads_fees") and ads_total_spend:
        summary["ads_fees"] = round(ads_total_spend, 2)

    # Order-count fallbacks
    if not summary.get("total_sale_orders"):
        summary["total_sale_orders"] = int((df["refund_amount"] >= 0).sum())
    if not summary.get("total_returns"):
        summary["total_returns"] = int((df["refund_amount"] < 0).sum())
