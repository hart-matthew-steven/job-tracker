"""add job application tags

Revision ID: 9c3d1a2b4e56
Revises: 1b7c1e2d3f45
Create Date: 2025-12-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c3d1a2b4e56"
down_revision: Union[str, Sequence[str], None] = "1b7c1e2d3f45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "job_application_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["job_applications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "application_id",
            "tag",
            name="uq_job_application_tags_application_id_tag",
        ),
    )
    op.create_index(op.f("ix_job_application_tags_id"), "job_application_tags", ["id"], unique=False)
    op.create_index(op.f("ix_job_application_tags_application_id"), "job_application_tags", ["application_id"], unique=False)
    op.create_index(op.f("ix_job_application_tags_tag"), "job_application_tags", ["tag"], unique=False)
    op.create_index(
        "ix_job_application_tags_application_id_tag",
        "job_application_tags",
        ["application_id", "tag"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_job_application_tags_application_id_tag", table_name="job_application_tags")
    op.drop_index(op.f("ix_job_application_tags_tag"), table_name="job_application_tags")
    op.drop_index(op.f("ix_job_application_tags_application_id"), table_name="job_application_tags")
    op.drop_index(op.f("ix_job_application_tags_id"), table_name="job_application_tags")
    op.drop_table("job_application_tags")


