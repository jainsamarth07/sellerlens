"""SQLAlchemy model for the optional Flipkart listing-file upload.

Keeps SKU → product-name (and stock / status / pricing) mappings so the
dashboard can replace raw SKU codes with human-readable titles.

This model lives in a separate file from ``seller_data`` so the existing
settlement-upload tables are untouched.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from backend.database import Base

DEFAULT_USER_ID = "default"


class ListingProduct(Base):
    """One row per (user_id, sku) — upserted on each listing-file upload."""

    __tablename__ = "listing_products"
    __table_args__ = (
        UniqueConstraint("user_id", "sku", name="uq_listing_user_sku"),
        Index("ix_listing_user_sku", "user_id", "sku"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, default=DEFAULT_USER_ID, index=True)
    sku = Column(String(255), nullable=False, index=True)
    product_name = Column(String(1000), nullable=True)
    mrp = Column(Float, nullable=True)
    selling_price = Column(Float, nullable=True)
    current_stock = Column(Integer, nullable=True)
    status = Column(String(32), nullable=True)
    category = Column(String(255), nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
