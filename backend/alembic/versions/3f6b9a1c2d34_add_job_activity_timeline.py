"""add job activity timeline

Revision ID: 3f6b9a1c2d34
Revises: 2a1f4d7c8e90
Create Date: 2025-12-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f6b9a1c2d34"
down_revision: Union[str, Sequence[str], None] = "2a1f4d7c8e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_activities_id"), "job_activities", ["id"], unique=False)
    op.create_index(op.f("ix_job_activities_application_id"), "job_activities", ["application_id"], unique=False)
    op.create_index(op.f("ix_job_activities_user_id"), "job_activities", ["user_id"], unique=False)
    op.create_index(op.f("ix_job_activities_type"), "job_activities", ["type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_activities_type"), table_name="job_activities")
    op.drop_index(op.f("ix_job_activities_user_id"), table_name="job_activities")
    op.drop_index(op.f("ix_job_activities_application_id"), table_name="job_activities")
    op.drop_index(op.f("ix_job_activities_id"), table_name="job_activities")
    op.drop_table("job_activities")


