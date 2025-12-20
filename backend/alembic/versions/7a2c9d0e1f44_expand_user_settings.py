"""expand user settings

Revision ID: 7a2c9d0e1f44
Revises: 5e8a0c1d2f33
Create Date: 2025-12-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a2c9d0e1f44"
down_revision: Union[str, Sequence[str], None] = "5e8a0c1d2f33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("theme", sa.String(length=20), server_default="dark", nullable=False))
    op.add_column("users", sa.Column("default_jobs_sort", sa.String(length=30), server_default="updated_desc", nullable=False))
    op.add_column("users", sa.Column("default_jobs_view", sa.String(length=30), server_default="all", nullable=False))
    op.add_column("users", sa.Column("data_retention_days", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "data_retention_days")
    op.drop_column("users", "default_jobs_view")
    op.drop_column("users", "default_jobs_sort")
    op.drop_column("users", "theme")


