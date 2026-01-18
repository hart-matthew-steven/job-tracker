"""Grant ai_conversations/ai_messages privileges to app user.

Revision ID: 20260106_05
Revises: 20260106_04
Create Date: 2026-01-07 12:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.core.config import settings

revision: str = "20260106_05"
down_revision: Union[str, None] = "20260106_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quote(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def upgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return
    quoted = _quote(app_user)

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ai_conversations TO {quoted}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ai_messages TO {quoted}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE ai_conversations_id_seq TO {quoted}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE ai_messages_id_seq TO {quoted}")


def downgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return
    quoted = _quote(app_user)

    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ai_conversations FROM {quoted}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ai_messages FROM {quoted}")
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE ai_conversations_id_seq FROM {quoted}")
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE ai_messages_id_seq FROM {quoted}")


