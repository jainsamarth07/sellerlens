"""Parse seller CSV / Excel files into normalised row dicts."""

import io

import pandas as pd


# Column name mappings — sellers may use different headers across platforms.
_COLUMN_ALIASES: dict[str, list[str]] = {
    "order_id": ["order id", "order_id", "orderid", "order no"],
    "sku": ["sku", "sku id", "product sku"],
    "product_name": ["product name", "product_name", "item name", "title"],
    "quantity": ["qty", "quantity", "units"],
    "selling_price": ["selling price", "selling_price", "sale price", "sp"],
    "cost_price": ["cost price", "cost_price", "purchase price", "cp"],
    "shipping_fee": ["shipping", "shipping fee", "shipping_fee", "delivery charge"],
    "platform_commission": [
        "commission",
        "platform commission",
        "platform_commission",
        "marketplace fee",
    ],
    "gst": ["gst", "tax", "gst amount"],
    "order_date": ["date", "order date", "order_date", "transaction date"],
}


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename columns to canonical names using the alias map."""
    lower_map = {c: c.strip().lower() for c in df.columns}
    df = df.rename(columns=lower_map)

    rename: dict[str, str] = {}
    for canonical, aliases in _COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in df.columns:
                rename[alias] = canonical
                break
    return df.rename(columns=rename)


def parse_seller_file(data: bytes, filename: str) -> list[dict]:
    """Parse raw file bytes into a list of normalised row dicts."""
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(data))
    else:
        df = pd.read_csv(io.BytesIO(data))

    df = _normalise_columns(df)

    # Coerce numeric columns
    for col in ["quantity", "selling_price", "cost_price", "shipping_fee", "platform_commission", "gst"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df.to_dict(orient="records")
