"""add auto_refresh_seconds to users

Revision ID: 1b7c1e2d3f45
Revises: 0f8b2b3a9c10
Create Date: 2025-12-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1b7c1e2d3f45"
down_revision: Union[str, Sequence[str], None] = "0f8b2b3a9c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auto_refresh_seconds", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "auto_refresh_seconds")


