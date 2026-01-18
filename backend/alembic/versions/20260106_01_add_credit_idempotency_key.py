"""Add idempotency key to credit ledger.

Revision ID: 20260106_01
Revises: 20260105_05
Create Date: 2026-01-06 08:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260106_01"
down_revision: Union[str, None] = "20260105_05"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "credit_ledger",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    # populate legacy rows with deterministic values
    op.execute(
        """
        UPDATE credit_ledger
        SET idempotency_key = 'legacy-' || id
        WHERE idempotency_key IS NULL
        """
    )
    op.alter_column("credit_ledger", "idempotency_key", nullable=False)
    op.create_unique_constraint(
        "uq_credit_ledger_user_idempotency",
        "credit_ledger",
        ["user_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_credit_ledger_user_idempotency", "credit_ledger", type_="unique")
    op.drop_column("credit_ledger", "idempotency_key")


