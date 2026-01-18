"""Add entry metadata columns to credit ledger.

Revision ID: 20260106_02
Revises: 20260106_01
Create Date: 2026-01-06 12:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260106_02"
down_revision: Union[str, None] = "20260106_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credit_ledger",
        sa.Column("entry_type", sa.String(length=50), nullable=False, server_default="credit_purchase"),
    )
    op.add_column(
        "credit_ledger",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="posted"),
    )
    op.add_column(
        "credit_ledger",
        sa.Column("correlation_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_credit_ledger_correlation_id",
        "credit_ledger",
        ["correlation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_ledger_correlation_id", table_name="credit_ledger")
    op.drop_column("credit_ledger", "correlation_id")
    op.drop_column("credit_ledger", "status")
    op.drop_column("credit_ledger", "entry_type")


