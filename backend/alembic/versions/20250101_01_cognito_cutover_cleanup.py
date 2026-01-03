"""cognito cutover cleanup

Revision ID: cognito_cutover_cleanup
Revises: h1c2d3e4f5a6
Create Date: 2026-01-01 02:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "cognito_cutover_cleanup"
down_revision = "h1c2d3e4f5a6"
branch_labels = None
depends_on = None


def _drop_table_if_exists(table_name: str) -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if table_name in inspector.get_table_names():
        op.drop_table(table_name)


def upgrade() -> None:
    _drop_table_if_exists("refresh_tokens")
    _drop_table_if_exists("email_verification_tokens")

    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    # Ensure all rows have a cognito_sub prior to making the column NOT NULL.
    if "cognito_sub" in columns:
        op.execute(
            sa.text(
                "UPDATE users SET cognito_sub = CONCAT('legacy-', id) WHERE cognito_sub IS NULL OR cognito_sub = ''"
            )
        )

    if "auth_provider" in columns:
        op.execute(
            sa.text(
                "UPDATE users SET auth_provider = 'cognito' WHERE auth_provider IS NULL OR auth_provider = ''"
            )
        )

    with op.batch_alter_table("users") as batch_op:
        if "cognito_sub" in columns:
            batch_op.alter_column("cognito_sub", existing_type=sa.String(length=255), nullable=False)
        if "auth_provider" in columns:
            batch_op.alter_column(
                "auth_provider",
                existing_type=sa.String(length=20),
                nullable=False,
                server_default="cognito",
            )
        for legacy_column in (
            "password_hash",
            "password_changed_at",
            "token_version",
            "is_email_verified",
            "email_verified_at",
        ):
            if legacy_column in columns:
                batch_op.drop_column(legacy_column)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("is_email_verified", sa.Boolean(), server_default="false", nullable=False))
        batch_op.add_column(sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch_op.alter_column("auth_provider", existing_type=sa.String(length=20), server_default="custom")
        batch_op.alter_column("cognito_sub", existing_type=sa.String(length=255), nullable=True)

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

