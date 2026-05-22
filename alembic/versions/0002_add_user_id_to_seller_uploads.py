"""Add user_id column to seller_uploads.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("seller_uploads", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_seller_uploads_user_id"), "seller_uploads", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_seller_uploads_user_id"), table_name="seller_uploads")
    op.drop_column("seller_uploads", "user_id")
