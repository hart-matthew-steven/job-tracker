"""Add momentum fields for board view.

Revision ID: board_momentum_fields
Revises: 20250107_01_add_ui_preferences
Create Date: 2026-01-04 19:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20250108_01"
down_revision: Union[str, None] = "20250107_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_applications",
        sa.Column("priority", sa.String(length=32), nullable=False, server_default="normal"),
    )
    op.add_column(
        "job_applications",
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "job_applications",
        sa.Column("next_action_title", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "job_applications",
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index(
        "ix_job_applications_priority",
        "job_applications",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_job_applications_next_action_at",
        "job_applications",
        ["next_action_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_job_applications_next_action_at", table_name="job_applications")
    op.drop_index("ix_job_applications_priority", table_name="job_applications")
    op.drop_column("job_applications", "last_action_at")
    op.drop_column("job_applications", "next_action_title")
    op.drop_column("job_applications", "next_action_at")
    op.drop_column("job_applications", "priority")

