"""Add AI conversations/messages and extend ai_usage.

Revision ID: 20260106_04
Revises: 20260106_03
Create Date: 2026-01-07 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260106_04"
down_revision: Union[str, None] = "20260106_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("credits_charged", sa.Integer(), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ai_messages_conversation_id_created_at", "ai_messages", ["conversation_id", "created_at"])

    op.add_column(
        "ai_usage",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("ai_conversations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "ai_usage",
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("ai_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("ai_usage", sa.Column("idempotency_key", sa.String(length=255), nullable=True))
    op.add_column("ai_usage", sa.Column("response_id", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE ai_usage
        SET idempotency_key = COALESCE(request_id, 'legacy-' || id)
        WHERE idempotency_key IS NULL
        """
    )
    op.alter_column("ai_usage", "idempotency_key", nullable=False)
    op.create_unique_constraint(
        "uq_ai_usage_user_idempotency",
        "ai_usage",
        ["user_id", "idempotency_key"],
    )
    op.create_index("ix_ai_usage_conversation_id", "ai_usage", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_conversation_id", table_name="ai_usage")
    op.drop_constraint("uq_ai_usage_user_idempotency", "ai_usage", type_="unique")
    op.drop_column("ai_usage", "response_id")
    op.drop_column("ai_usage", "idempotency_key")
    op.drop_column("ai_usage", "message_id")
    op.drop_column("ai_usage", "conversation_id")

    op.drop_index("ix_ai_messages_conversation_id_created_at", table_name="ai_messages")
    op.drop_table("ai_messages")

    op.drop_index("ix_ai_conversations_user_id", table_name="ai_conversations")
    op.drop_table("ai_conversations")


