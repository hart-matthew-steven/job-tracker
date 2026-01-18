"""Grant credit ledger/ai_usage privileges to app user.

Revision ID: 20260105_04
Revises: 20260105_03
Create Date: 2026-01-05 18:40:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.core.config import settings

revision: str = "20260105_04"
down_revision: Union[str, None] = "20260105_03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quote_ident(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def upgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return
    quoted = _quote_ident(app_user)

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON credit_ledger TO {quoted}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ai_usage TO {quoted}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE credit_ledger_id_seq TO {quoted}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE ai_usage_id_seq TO {quoted}")


def downgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return
    quoted = _quote_ident(app_user)

    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON credit_ledger FROM {quoted}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON ai_usage FROM {quoted}")
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE credit_ledger_id_seq FROM {quoted}")
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE ai_usage_id_seq FROM {quoted}")


