"""remove user profile artifacts and enforce user.name not null

Revision ID: h1c2d3e4f5a6
Revises: g8b9c0d1e2f3
Create Date: 2025-12-31 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "h1c2d3e4f5a6"
down_revision: str = "g8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Drop legacy user_profiles table if it exists
    tables = inspector.get_table_names()
    if "user_profiles" in tables:
        op.execute("DROP TABLE IF EXISTS user_profiles CASCADE")

    # Drop profile_completed_at column from users if it exists
    user_columns = {col["name"] for col in inspector.get_columns("users")}
    if "profile_completed_at" in user_columns:
        with op.batch_alter_table("users") as batch:
            batch.drop_column("profile_completed_at")

    # Ensure name column is populated before making it NOT NULL
    op.execute(
        """
        UPDATE users
        SET name = COALESCE(NULLIF(TRIM(name), ''), 'Unnamed User')
        WHERE name IS NULL OR TRIM(name) = ''
        """
    )

    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "name",
            existing_type=sa.String(length=100),
            nullable=False,
        )


def downgrade() -> None:
    # Downgrade restores name to nullable and re-adds profile_completed_at column.
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "name",
            existing_type=sa.String(length=100),
            nullable=True,
        )
        batch.add_column(
            sa.Column("profile_completed_at", sa.DateTime(timezone=True), nullable=True)
        )

    # Recreate user_profiles table (structure matches the original Chunk 3 migration)
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.String(length=255), unique=True, index=True, nullable=False),
        sa.Column("auth_provider", sa.String(length=20), nullable=False),
        sa.Column("external_subject", sa.String(length=255), nullable=True, index=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("profile_completed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )


