"""Profit calculation logic for seller order data."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.seller_data import OrderRow


def compute_profit_summary(db: Session, upload_id: int) -> dict | None:
    """Aggregate profit metrics for all orders belonging to *upload_id*."""
    rows = db.query(OrderRow).filter(OrderRow.upload_id == upload_id).all()
    if not rows:
        return None

    total_revenue = sum(r.selling_price * r.quantity for r in rows)
    total_cost = sum(r.cost_price * r.quantity for r in rows)
    total_shipping = sum(r.shipping_fee for r in rows)
    total_commission = sum(r.platform_commission for r in rows)
    total_gst = sum(r.gst for r in rows)
    total_profit = total_revenue - total_cost - total_shipping - total_commission - total_gst

    return {
        "upload_id": upload_id,
        "total_orders": len(rows),
        "total_revenue": round(total_revenue, 2),
        "total_cost": round(total_cost, 2),
        "total_shipping": round(total_shipping, 2),
        "total_commission": round(total_commission, 2),
        "total_gst": round(total_gst, 2),
        "net_profit": round(total_profit, 2),
        "profit_margin_pct": round((total_profit / total_revenue * 100), 2) if total_revenue else 0,
    }
