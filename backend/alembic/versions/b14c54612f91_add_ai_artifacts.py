"""add ai artifacts

Revision ID: b14c54612f91
Revises: 20260108_02
Create Date: 2026-01-10 21:03:01.057932

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b14c54612f91"
down_revision: Union[str, Sequence[str], None] = "20260108_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


artifact_type = sa.Enum("resume", "job_description", "note", name="artifact_type_enum")
artifact_source = sa.Enum("upload", "url", "paste", name="artifact_source_enum")
artifact_status = sa.Enum("pending", "ready", "failed", name="artifact_status_enum")


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "ai_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("artifact_type", artifact_type, nullable=False),
        sa.Column("source_type", artifact_source, nullable=False),
        sa.Column("source_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("s3_key", sa.String(length=512), nullable=True),
        sa.Column("text_content", sa.Text(), nullable=True),
        sa.Column("status", artifact_status, nullable=False, server_default="pending"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("previous_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["previous_version_id"], ["ai_artifacts.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "artifact_type", "version_number", name="uq_artifact_version"),
    )
    op.create_index("ix_ai_artifacts_user_id", "ai_artifacts", ["user_id"])
    op.create_index("ix_ai_artifacts_conversation_id", "ai_artifacts", ["conversation_id"])

    op.create_table(
        "ai_conversation_artifacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=False),
        sa.Column("role", artifact_type, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pinned_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["ai_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artifact_id"], ["ai_artifacts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("conversation_id", "role", name="uq_conversation_role"),
    )
    op.create_index(
        "ix_ai_conversation_artifacts_conversation_id",
        "ai_conversation_artifacts",
        ["conversation_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_ai_conversation_artifacts_conversation_id", table_name="ai_conversation_artifacts")
    op.drop_table("ai_conversation_artifacts")

    op.drop_index("ix_ai_artifacts_conversation_id", table_name="ai_artifacts")
    op.drop_index("ix_ai_artifacts_user_id", table_name="ai_artifacts")
    op.drop_table("ai_artifacts")

    bind = op.get_bind()
    artifact_status.drop(bind, checkfirst=True)
    artifact_source.drop(bind, checkfirst=True)
    artifact_type.drop(bind, checkfirst=True)
