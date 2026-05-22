"""Optional Flipkart listing-file ingestion.

A listing file is a Flipkart "Listings" export (.xlsx / .csv) whose Sheet1
contains the seller's catalogue. We extract a fixed subset of columns and
upsert them into the ``listing_products`` table so the dashboard can
render product names instead of raw SKU codes.

Nothing in this module mutates settlement-side state — it is purely additive.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Iterable

import pandas as pd
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.database import Base, engine
from backend.models.listing import DEFAULT_USER_ID, ListingProduct
from backend.processors._helpers import safe_str, to_float, to_int

logger = logging.getLogger(__name__)

# Exact Flipkart listing-file column names (Sheet1 header row).
LISTING_COLUMNS = {
    "sku": "Your Identifier for a product",
    "product_name": "Title of your product as on Flipkart.com",
    "mrp": "MRP of your product",
    "selling_price": "Selling Price of your product",
    "current_stock": "Current stock count for your product",
    "status": "Status of your product",
    "category": "Category of the product",
}


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

def ensure_listing_table(target_engine: Engine | None = None) -> None:
    """Create the ``listing_products`` table on first use (no-op if it exists)."""
    Base.metadata.create_all(
        bind=target_engine or engine,
        tables=[ListingProduct.__table__],
        checkfirst=True,
    )


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_listing_file(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    """Parse a Flipkart listing file and return one dict per product row.

    Supports both ``.xlsx`` (reads Sheet1) and ``.csv``. Unknown / missing
    optional columns degrade gracefully — only ``sku`` is required.
    """
    name = (filename or "").lower()
    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes))
    else:
        xl = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")
        sheet = xl.sheet_names[0] if "Sheet1" not in xl.sheet_names else "Sheet1"
        df = xl.parse(sheet)

    if df.empty:
        return []

    # Strip whitespace from header names for forgiving exact-matching.
    df.columns = [str(c).strip() for c in df.columns]

    sku_col = LISTING_COLUMNS["sku"]
    if sku_col not in df.columns:
        raise ValueError(
            f"Listing file is missing the required column: '{sku_col}'."
        )

    out: list[dict[str, Any]] = []
    seen_skus: set[str] = set()
    for _, row in df.iterrows():
        sku = safe_str(row[sku_col])
        if not sku or sku in seen_skus:
            continue
        seen_skus.add(sku)

        product_name = safe_str(row.get(LISTING_COLUMNS["product_name"])) or None
        category = safe_str(row.get(LISTING_COLUMNS["category"])) or None
        status_raw = safe_str(row.get(LISTING_COLUMNS["status"])) or None
        status = status_raw.upper() if status_raw else None

        out.append(
            {
                "sku": sku,
                "product_name": product_name,
                "mrp": to_float(row.get(LISTING_COLUMNS["mrp"]), default=0.0) or None,
                "selling_price": (
                    to_float(row.get(LISTING_COLUMNS["selling_price"]), default=0.0) or None
                ),
                "current_stock": to_int(row.get(LISTING_COLUMNS["current_stock"]), default=0),
                "status": status,
                "category": category,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Persistence (upsert by (user_id, sku))
# ---------------------------------------------------------------------------

def save_listings(
    db: Session, user_id: str, rows: Iterable[dict[str, Any]]
) -> int:
    """Upsert listing rows for ``user_id``. Returns the number of rows written."""
    ensure_listing_table(db.get_bind())

    rows = list(rows)
    if not rows:
        return 0

    skus = [r["sku"] for r in rows]
    existing = {
        lp.sku: lp
        for lp in db.execute(
            select(ListingProduct).where(
                ListingProduct.user_id == user_id, ListingProduct.sku.in_(skus)
            )
        ).scalars()
    }

    written = 0
    for r in rows:
        record = existing.get(r["sku"])
        if record is None:
            record = ListingProduct(user_id=user_id, sku=r["sku"])
            db.add(record)
        record.product_name = r.get("product_name")
        record.mrp = r.get("mrp")
        record.selling_price = r.get("selling_price")
        record.current_stock = r.get("current_stock")
        record.status = r.get("status")
        record.category = r.get("category")
        written += 1

    db.commit()
    return written


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

def listing_lookup(db: Session, user_id: str = DEFAULT_USER_ID) -> dict[str, dict[str, Any]]:
    """Return ``{sku: product_info_dict}`` for the given user. Empty on no-table."""
    try:
        ensure_listing_table(db.get_bind())
        rows = db.execute(
            select(ListingProduct).where(ListingProduct.user_id == user_id)
        ).scalars().all()
    except Exception as exc:  # noqa: BLE001 — fail soft so settlement upload still works
        logger.warning("listing_lookup failed: %s", exc)
        return {}

    return {
        r.sku: {
            "product_name": r.product_name,
            "mrp": r.mrp,
            "selling_price": r.selling_price,
            "current_stock": r.current_stock,
            "status": r.status,
            "category": r.category,
        }
        for r in rows
    }


def resolve_sku_names(
    skus: list[dict[str, Any]],
    db: Session | None,
    user_id: str = DEFAULT_USER_ID,
) -> list[dict[str, Any]]:
    """Enrich each SKU row with product metadata from the listing table.

    - Mutates each dict in place (also returns the list for convenience).
    - Unknown SKUs get ``product_name = None`` so the frontend can fall back.
    - Always safe to call: if ``db`` is None or the table doesn't exist yet,
      every SKU is left with ``product_name = None``.
    """
    if not skus:
        return skus

    lookup = listing_lookup(db, user_id=user_id) if db is not None else {}

    for sku_row in skus:
        sku_code = sku_row.get("seller_sku")
        info = lookup.get(sku_code) if sku_code else None
        if info:
            sku_row["product_name"] = info.get("product_name")
            sku_row["mrp"] = info.get("mrp")
            sku_row["listing_selling_price"] = info.get("selling_price")
            sku_row["current_stock"] = info.get("current_stock")
            sku_row["listing_status"] = info.get("status")
            sku_row["category"] = info.get("category")
        else:
            sku_row.setdefault("product_name", None)
            sku_row.setdefault("mrp", None)
            sku_row.setdefault("listing_selling_price", None)
            sku_row.setdefault("current_stock", None)
            sku_row.setdefault("listing_status", None)
            sku_row.setdefault("category", None)
    return skus


def match_summary(
    db: Session, user_id: str, sku_codes: Iterable[str]
) -> dict[str, Any]:
    """Return ``{matched, total, unmatched_skus}`` for a set of SKU codes."""
    codes = [c for c in sku_codes if c]
    lookup = listing_lookup(db, user_id=user_id)
    matched = [c for c in codes if c in lookup]
    unmatched = sorted({c for c in codes if c not in lookup})
    return {
        "matched": len(matched),
        "total": len(codes),
        "unmatched_skus": unmatched,
        "listing_count": len(lookup),
    }
