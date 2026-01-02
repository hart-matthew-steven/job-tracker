"""add cognito fields to users

Revision ID: g8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2025-12-31 16:00:00.000000

This migration adds Cognito support to the users table:
- cognito_sub: Cognito user identifier (unique, nullable)
- auth_provider: How user was provisioned (custom/cognito)
- profile_completed_at: When user completed their profile (nullable)
- Makes password_hash nullable (Cognito users don't have passwords)
- Makes password_changed_at nullable (same reason)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "g8b9c0d1e2f3"
down_revision: str = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add cognito_sub column (unique, nullable for custom auth users)
    op.add_column(
        "users",
        sa.Column("cognito_sub", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)

    # Add auth_provider column (default to "custom" for existing users)
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(length=20), nullable=False, server_default="custom"),
    )

    # Add profile_completed_at for Cognito users
    op.add_column(
        "users",
        sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Make password_hash nullable (Cognito users don't need passwords)
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    # Make password_changed_at nullable (Cognito users don't have passwords)
    op.alter_column(
        "users",
        "password_changed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    # Revert password_changed_at to NOT NULL (will fail if any NULL values exist)
    op.alter_column(
        "users",
        "password_changed_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    # Revert password_hash to NOT NULL (will fail if any NULL values exist)
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )

    # Remove profile_completed_at
    op.drop_column("users", "profile_completed_at")

    # Remove auth_provider
    op.drop_column("users", "auth_provider")

    # Remove cognito_sub
    op.drop_index("ix_users_cognito_sub", table_name="users")
    op.drop_column("users", "cognito_sub")

