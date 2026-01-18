"""grant ai artifact tables privileges

Revision ID: ddc5f3afbfd8
Revises: b14c54612f91
Create Date: 2026-01-10 21:13:45.571461

"""
from typing import Sequence, Union

from alembic import op

from app.core.config import settings


# revision identifiers, used by Alembic.
revision: str = "ddc5f3afbfd8"
down_revision: Union[str, Sequence[str], None] = "b14c54612f91"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quote(identifier: str) -> str:
    return f'"{identifier.replace("\"", "\"\"")}"'


def _grant(app_user: str) -> None:
    quoted = _quote(app_user)
    for table in ("ai_artifacts", "ai_conversation_artifacts"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {quoted}")
    for seq in ("ai_artifacts_id_seq", "ai_conversation_artifacts_id_seq"):
        op.execute(f"GRANT USAGE, SELECT ON SEQUENCE {seq} TO {quoted}")
    for enum_type in ("artifact_type_enum", "artifact_source_enum", "artifact_status_enum"):
        op.execute(f"GRANT USAGE ON TYPE {enum_type} TO {quoted}")


def _revoke(app_user: str) -> None:
    quoted = _quote(app_user)
    for table in ("ai_artifacts", "ai_conversation_artifacts"):
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM {quoted}")
    for seq in ("ai_artifacts_id_seq", "ai_conversation_artifacts_id_seq"):
        op.execute(f"REVOKE USAGE, SELECT ON SEQUENCE {seq} FROM {quoted}")
    for enum_type in ("artifact_type_enum", "artifact_source_enum", "artifact_status_enum"):
        op.execute(f"REVOKE USAGE ON TYPE {enum_type} FROM {quoted}")


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
