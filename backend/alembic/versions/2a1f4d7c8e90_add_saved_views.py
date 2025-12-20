"""add saved views

Revision ID: 2a1f4d7c8e90
Revises: 9c3d1a2b4e56
Create Date: 2025-12-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2a1f4d7c8e90"
down_revision: Union[str, Sequence[str], None] = "9c3d1a2b4e56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "saved_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_views_user_id_name"),
    )
    op.create_index(op.f("ix_saved_views_id"), "saved_views", ["id"], unique=False)
    op.create_index(op.f("ix_saved_views_user_id"), "saved_views", ["user_id"], unique=False)
    op.create_index(op.f("ix_saved_views_name"), "saved_views", ["name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_saved_views_name"), table_name="saved_views")
    op.drop_index(op.f("ix_saved_views_user_id"), table_name="saved_views")
    op.drop_index(op.f("ix_saved_views_id"), table_name="saved_views")
    op.drop_table("saved_views")


