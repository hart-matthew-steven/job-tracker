"""Enhance AI usage table for responses and status.

Revision ID: 20260106_03
Revises: 20260106_02
Create Date: 2026-01-07 09:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260106_03"
down_revision: Union[str, None] = "20260106_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_usage", sa.Column("reserved_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_usage", sa.Column("actual_cents", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("ai_usage", sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"))
    op.add_column("ai_usage", sa.Column("response_text", sa.Text(), nullable=True))
    op.add_column("ai_usage", sa.Column("error_message", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE ai_usage
        SET status = 'succeeded'
        WHERE cost_cents > 0
        """
    )


def downgrade() -> None:
    op.drop_column("ai_usage", "error_message")
    op.drop_column("ai_usage", "response_text")
    op.drop_column("ai_usage", "status")
    op.drop_column("ai_usage", "actual_cents")
    op.drop_column("ai_usage", "reserved_cents")


