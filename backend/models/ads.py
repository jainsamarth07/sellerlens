"""SQLAlchemy model for the optional Flipkart ads-report upload.

One row per uploaded campaign, scoped by ``user_id`` (matches the JWT
user id from the auth layer). Tables are created on first use via
:func:`backend.services.ads_service.ensure_ads_table` so no separate
migration step is required.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    String,
)

from backend.database import Base


class AdCampaign(Base):
    """One Flipkart ad campaign row from a seller's monthly ads report."""

    __tablename__ = "ad_campaigns"
    __table_args__ = (
        Index("ix_ad_campaigns_user_period", "user_id", "settlement_period"),
        Index("ix_ad_campaigns_user_campaign", "user_id", "campaign_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    settlement_period = Column(String(100), nullable=True)

    campaign_id = Column(String(100), nullable=True)
    campaign_name = Column(String(500), nullable=True)
    campaign_status = Column(String(50), nullable=True)
    budget_type = Column(String(50), nullable=True)
    campaign_budget = Column(Numeric(12, 2), nullable=True)

    ad_spend = Column(Numeric(12, 2), nullable=False, default=0)
    views = Column(Integer, nullable=True)
    clicks = Column(Integer, nullable=True)
    conversions = Column(Numeric(10, 2), nullable=True)
    revenue = Column(Numeric(12, 2), nullable=True)
    roi = Column(Numeric(10, 4), nullable=True)
    ctr = Column(Numeric(10, 6), nullable=True)
    conversion_rate = Column(Numeric(10, 6), nullable=True)

    mapped_category = Column(String(255), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
