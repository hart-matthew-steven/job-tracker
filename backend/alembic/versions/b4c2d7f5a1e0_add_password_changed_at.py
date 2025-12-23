"""add password_changed_at

Revision ID: b4c2d7f5a1e0
Revises: 8c1a2f4b7d11
Create Date: 2025-12-23 19:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4c2d7f5a1e0"
down_revision: Union[str, Sequence[str], None] = "8c1a2f4b7d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))

    conn = op.get_bind()
    conn.execute(sa.text("UPDATE users SET password_changed_at = COALESCE(password_changed_at, created_at, NOW())"))

    op.alter_column(
        "users",
        "password_changed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")

