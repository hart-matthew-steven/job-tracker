"""add job interviews

Revision ID: 5e8a0c1d2f33
Revises: 3f6b9a1c2d34
Create Date: 2025-12-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5e8a0c1d2f33"
down_revision: Union[str, Sequence[str], None] = "3f6b9a1c2d34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_interviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stage", sa.String(length=50), nullable=True),
        sa.Column("kind", sa.String(length=50), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("interviewer", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="scheduled", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["job_applications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_interviews_id"), "job_interviews", ["id"], unique=False)
    op.create_index(op.f("ix_job_interviews_application_id"), "job_interviews", ["application_id"], unique=False)
    op.create_index(op.f("ix_job_interviews_user_id"), "job_interviews", ["user_id"], unique=False)
    op.create_index(op.f("ix_job_interviews_scheduled_at"), "job_interviews", ["scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_interviews_scheduled_at"), table_name="job_interviews")
    op.drop_index(op.f("ix_job_interviews_user_id"), table_name="job_interviews")
    op.drop_index(op.f("ix_job_interviews_application_id"), table_name="job_interviews")
    op.drop_index(op.f("ix_job_interviews_id"), table_name="job_interviews")
    op.drop_table("job_interviews")


