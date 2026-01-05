"""add ui preferences column

Revision ID: 20250107_01
Revises: 20250106_01
Create Date: 2026-01-07 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20250107_01"
down_revision = "20250106_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "ui_preferences",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "ui_preferences")


