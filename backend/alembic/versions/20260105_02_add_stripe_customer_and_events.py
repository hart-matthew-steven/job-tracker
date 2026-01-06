"""Add Stripe customer linkage and events table.

Revision ID: 20260105_02
Revises: 20260105_01
Create Date: 2026-01-05 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260105_02"
down_revision: Union[str, None] = "20260105_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("stripe_customer_id", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_stripe_customer_id", "users", ["stripe_customer_id"])

    op.create_table(
        "stripe_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_event_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint(
        "uq_stripe_events_event_id",
        "stripe_events",
        ["stripe_event_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_stripe_events_event_id", "stripe_events", type_="unique")
    op.drop_table("stripe_events")

    op.drop_constraint("uq_users_stripe_customer_id", "users", type_="unique")
    op.drop_column("users", "stripe_customer_id")


