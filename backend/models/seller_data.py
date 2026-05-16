"""SQLAlchemy models for seller uploads and order-level data."""

import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from backend.database import Base


class SellerUpload(Base):
    """Tracks each file upload from a seller."""

    __tablename__ = "seller_uploads"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False, default="flipkart")
    blob_url = Column(Text, nullable=False)
    row_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    orders = relationship("OrderRow", back_populates="upload", cascade="all, delete-orphan")


class OrderRow(Base):
    """Individual order / transaction row extracted from a seller file."""

    __tablename__ = "order_rows"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("seller_uploads.id"), nullable=False)

    order_id = Column(String(100))
    sku = Column(String(100))
    product_name = Column(String(500))
    quantity = Column(Integer, default=1)
    selling_price = Column(Float, default=0.0)
    cost_price = Column(Float, default=0.0)
    shipping_fee = Column(Float, default=0.0)
    platform_commission = Column(Float, default=0.0)
    gst = Column(Float, default=0.0)
    net_profit = Column(Float, default=0.0)
    order_date = Column(DateTime, nullable=True)

    upload = relationship("SellerUpload", back_populates="orders")
