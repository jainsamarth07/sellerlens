"""Initial schema — seller_uploads and order_rows tables.

Revision ID: 0001
Revises:
Create Date: 2026-05-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seller_uploads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=50), nullable=False),
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_seller_uploads_id"), "seller_uploads", ["id"], unique=False)

    op.create_table(
        "order_rows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.String(length=100), nullable=True),
        sa.Column("sku", sa.String(length=100), nullable=True),
        sa.Column("product_name", sa.String(length=500), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=True),
        sa.Column("selling_price", sa.Float(), nullable=True),
        sa.Column("cost_price", sa.Float(), nullable=True),
        sa.Column("shipping_fee", sa.Float(), nullable=True),
        sa.Column("platform_commission", sa.Float(), nullable=True),
        sa.Column("gst", sa.Float(), nullable=True),
        sa.Column("net_profit", sa.Float(), nullable=True),
        sa.Column("order_date", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["upload_id"], ["seller_uploads.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_order_rows_id"), "order_rows", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_order_rows_id"), table_name="order_rows")
    op.drop_table("order_rows")
    op.drop_index(op.f("ix_seller_uploads_id"), table_name="seller_uploads")
    op.drop_table("seller_uploads")
