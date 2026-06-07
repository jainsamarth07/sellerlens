"""Add summary_json, skus_json, ads_total_spend to seller_uploads.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("seller_uploads", sa.Column("summary_json", sa.Text(), nullable=True))
    op.add_column("seller_uploads", sa.Column("skus_json", sa.Text(), nullable=True))
    op.add_column("seller_uploads", sa.Column("ads_total_spend", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("seller_uploads", "ads_total_spend")
    op.drop_column("seller_uploads", "skus_json")
    op.drop_column("seller_uploads", "summary_json")
