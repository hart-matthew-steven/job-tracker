"""Add status fields to stripe_events and pack metadata to credit_ledger.

Revision ID: 20260105_05
Revises: 20260105_04
Create Date: 2026-01-05 19:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260105_05"
down_revision: Union[str, None] = "20260105_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "stripe_events",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
    )
    op.add_column("stripe_events", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("stripe_events", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))

    # Update existing rows to processed since they were previously handled.
    op.execute("UPDATE stripe_events SET status = 'processed' WHERE status IS NULL OR status = ''")

    op.add_column("credit_ledger", sa.Column("pack_key", sa.String(length=50), nullable=True))
    op.add_column(
        "credit_ledger",
        sa.Column("stripe_checkout_session_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "credit_ledger",
        sa.Column("stripe_payment_intent_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_credit_ledger_stripe_checkout_session_id",
        "credit_ledger",
        ["stripe_checkout_session_id"],
    )
    op.create_index(
        "ix_credit_ledger_stripe_payment_intent_id",
        "credit_ledger",
        ["stripe_payment_intent_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_credit_ledger_stripe_payment_intent_id", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_stripe_checkout_session_id", table_name="credit_ledger")
    op.drop_column("credit_ledger", "stripe_payment_intent_id")
    op.drop_column("credit_ledger", "stripe_checkout_session_id")
    op.drop_column("credit_ledger", "pack_key")

    op.drop_column("stripe_events", "processed_at")
    op.drop_column("stripe_events", "error_message")
    op.drop_column("stripe_events", "status")


