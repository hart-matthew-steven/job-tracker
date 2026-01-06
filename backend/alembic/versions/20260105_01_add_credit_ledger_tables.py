"""Add credit ledger and AI usage tables.

Revision ID: 20260105_01
Revises: 20250108_01
Create Date: 2026-01-05 10:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260105_01"
down_revision: Union[str, None] = "20250108_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="usd"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "source_ref", name="uq_credit_ledger_user_source_ref"),
    )
    op.create_index(
        "ix_credit_ledger_user_id_created_at",
        "credit_ledger",
        ["user_id", "created_at"],
    )

    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feature", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_cents", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "request_id", name="uq_ai_usage_user_request_id"),
    )
    op.create_index(
        "ix_ai_usage_user_id_created_at",
        "ai_usage",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_user_id_created_at", table_name="ai_usage")
    op.drop_table("ai_usage")

    op.drop_index("ix_credit_ledger_user_id_created_at", table_name="credit_ledger")
    op.drop_table("credit_ledger")


