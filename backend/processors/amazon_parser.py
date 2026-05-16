"""Parser for Amazon MTR / Settlement CSV reports.

Amazon's settlement CSV doesn't have multiple sheets — it's a single tabular
file where each row is a transaction (order, refund, fee, ad spend, etc).
We aggregate it into the same canonical shape that
``flipkart_parser.parse_flipkart_settlement`` returns so downstream code can
treat both platforms uniformly.
"""

from __future__ import annotations

import io
from typing import Any

import pandas as pd

from backend.processors._helpers import find_column, safe_str, to_float, to_int
from backend.processors.flipkart_parser import aggregate_skus

# Map canonical order field → Amazon settlement column candidates
_AMZ_FIELD_MAP: dict[str, list[str]] = {
    "order_id": ["order id", "amazon order id"],
    "order_item_id": ["shipment item id", "order item id"],
    "payment_date": ["posted date time", "posted date", "settlement date"],
    "sale_amount": ["product sales", "principal amount", "item price"],
    "marketplace_fee": ["selling fees", "fba fees", "marketplace fees"],
    "taxes": ["taxes", "marketplace facilitator tax", "product sales tax"],
    "refund_amount": ["refund amount", "promotional rebates", "refund"],
    "bank_settlement_value": ["total", "net amount", "settlement amount"],
    "seller_sku": ["sku", "merchant sku"],
    "quantity": ["quantity purchased", "quantity"],
    "product_sub_category": ["product category", "category"],
    "return_type": ["transaction type"],
    "commission": ["commission"],
    "fixed_fee": ["fixed closing fee", "fixed fee"],
    "collection_fee": ["collection fee"],
    "reverse_shipping_fee": ["return shipping", "reverse shipping fee"],
    "tcs": ["tcs cgst", "tcs sgst", "tcs igst", "tcs"],
    "tds": ["tds"],
    "gst_on_mp_fees": ["gst on selling fees", "gst on mp fees"],
}

_NUMERIC_FIELDS = {
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


def _read_csv(data: bytes) -> pd.DataFrame:
    """Read an Amazon CSV, tolerating both UTF-8 and Latin-1 encodings."""
    try:
        return pd.read_csv(io.BytesIO(data))
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(data), encoding="latin-1")


def parse_amazon_settlement(file_bytes: bytes) -> dict[str, Any]:
    """Parse an Amazon settlement CSV into the canonical analytics dict."""
    parsing_errors: list[str] = []
    result: dict[str, Any] = {
        "platform": "amazon",
        "summary": {},
        "orders": [],
        "ads_total_spend": 0.0,
        "ads": [],
        "skus": [],
        "parsing_errors": parsing_errors,
    }

    try:
        df = _read_csv(file_bytes)
    except Exception as exc:  # noqa: BLE001
        parsing_errors.append(f"Failed to read CSV: {exc}")
        return result

    if df.empty:
        parsing_errors.append("CSV is empty")
        return result

    # --- Resolve columns ----------------------------------------------------
    col_lookup: dict[str, str | None] = {
        f: find_column(df, *aliases) for f, aliases in _AMZ_FIELD_MAP.items()
    }

    txn_col = find_column(df, "transaction type", "type")

    orders: list[dict] = []
    ads_rows: list[dict] = []
    ads_total = 0.0

    for idx, row in df.iterrows():
        try:
            txn_type = safe_str(row[txn_col]).lower() if txn_col else ""

            # Route ad-related rows to the ads bucket
            if txn_type and any(k in txn_type for k in ("ad", "advertis", "sponsored")):
                amount = (
                    to_float(row[col_lookup["bank_settlement_value"]])
                    if col_lookup["bank_settlement_value"]
                    else 0.0
                )
                gst = (
                    to_float(row[col_lookup["gst_on_mp_fees"]])
                    if col_lookup["gst_on_mp_fees"]
                    else 0.0
                )
                ads_rows.append(
                    {
                        "campaign_id": safe_str(row[col_lookup["order_id"]]) if col_lookup["order_id"] else "",
                        "transaction_type": txn_type,
                        "amount": amount,
                        "gst_on_ads": gst,
                    }
                )
                ads_total += amount + gst
                continue

            record: dict[str, Any] = {}
            for field, col in col_lookup.items():
                raw = row[col] if col is not None and col in row else None
                if field in _NUMERIC_FIELDS:
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

            if not record.get("order_id") and not record.get("sale_amount"):
                continue
            orders.append(record)
        except Exception as exc:  # noqa: BLE001
            parsing_errors.append(f"Row {idx}: {exc}")

    # --- Synthesise a summary from the row data -----------------------------
    total_revenue = sum(o["sale_amount"] for o in orders)
    total_refunds = sum(o["refund_amount"] for o in orders if o["refund_amount"] < 0)
    total_mp_fees = sum(o["marketplace_fee"] for o in orders)
    total_taxes = sum(o["taxes"] for o in orders)
    net_settlement = sum(o["bank_settlement_value"] for o in orders)
    return_count = sum(1 for o in orders if o["refund_amount"] < 0)

    result["summary"] = {
        "payment_duration": "",
        "total_sale_orders": len(orders),
        "total_returns": return_count,
        "gross_sales_amount": round(total_revenue, 2),
        "returns_reversal": round(total_refunds, 2),
        "marketplace_fees": round(total_mp_fees, 2),
        "tcs_amount": round(sum(o["tcs"] for o in orders), 2),
        "tds_amount": round(sum(o["tds"] for o in orders), 2),
        "gst_on_mp_fees": round(sum(o["gst_on_mp_fees"] for o in orders), 2),
        "ads_fees": round(ads_total, 2),
        "net_bank_settlement": round(net_settlement, 2),
        "input_gst_tcs_credits": 0.0,
        "income_tax_credits": 0.0,
        "total_realizable_amount": round(net_settlement + total_taxes, 2),
    }

    result["orders"] = orders
    result["ads"] = ads_rows
    result["ads_total_spend"] = round(ads_total, 2)
    result["skus"] = aggregate_skus(orders)

    return result
