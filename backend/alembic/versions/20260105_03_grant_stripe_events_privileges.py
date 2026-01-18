"""Grant stripe_events privileges to app user.

Revision ID: 20260105_03
Revises: 20260105_02
Create Date: 2026-01-05 18:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "20260105_03"
down_revision: Union[str, None] = "20260105_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quote_ident(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def upgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return

    quoted_user = _quote_ident(app_user)
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON stripe_events TO {quoted_user}")
    op.execute(f"GRANT USAGE, SELECT ON SEQUENCE stripe_events_id_seq TO {quoted_user}")


def downgrade() -> None:
    app_user = (settings.DB_APP_USER or "").strip()
    if not app_user:
        return

    quoted_user = _quote_ident(app_user)
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON stripe_events FROM {quoted_user}")
    op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE stripe_events_id_seq FROM {quoted_user}")


