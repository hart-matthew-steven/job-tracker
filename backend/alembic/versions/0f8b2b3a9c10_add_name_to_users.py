"""add name to users

Revision ID: 0f8b2b3a9c10
Revises: 72c83e870fc3
Create Date: 2025-12-18

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0f8b2b3a9c10"
down_revision: Union[str, Sequence[str], None] = "72c83e870fc3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "name")


