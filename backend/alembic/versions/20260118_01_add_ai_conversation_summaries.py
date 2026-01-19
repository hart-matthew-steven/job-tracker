"""add ai conversation summaries

Revision ID: 20260118_01
Revises: ddc5f3afbfd8
Create Date: 2026-01-18 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260118_01"
down_revision: Union[str, Sequence[str], None] = "ddc5f3afbfd8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_conversation_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("covering_message_id", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_ai_conversation_summaries_conversation_id",
        "ai_conversation_summaries",
        ["conversation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_conversation_summaries_conversation_id", table_name="ai_conversation_summaries")
    op.drop_table("ai_conversation_summaries")
