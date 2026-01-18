"""Add balance_remaining_cents to AI messages."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260108_02"
down_revision: str | None = "20260108_01"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_messages", sa.Column("balance_remaining_cents", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_messages", "balance_remaining_cents")

