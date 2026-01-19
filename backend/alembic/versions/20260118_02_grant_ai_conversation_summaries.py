"""grant ai conversation summaries privileges

Revision ID: 20260118_02
Revises: 20260118_01
Create Date: 2026-01-18 21:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = "20260118_02"
down_revision: Union[str, Sequence[str], None] = "20260118_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quote(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def _grant(app_user: str) -> None:
    quoted = _quote(app_user)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ai_conversation_summaries TO {quoted}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE ai_conversation_summaries_id_seq TO {quoted}")


def _revoke(app_user: str) -> None:
    quoted = _quote(app_user)
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ai_conversation_summaries FROM {quoted}")
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE ai_conversation_summaries_id_seq FROM {quoted}")


def upgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return
    _grant(app_user)


def downgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return
    _revoke(app_user)
