"""add document scan fields

Revision ID: 8c1a2f4b7d11
Revises: 7a2c9d0e1f44
Create Date: 2025-12-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c1a2f4b7d11"
down_revision: Union[str, Sequence[str], None] = "7a2c9d0e1f44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add scan fields
    op.add_column(
        "job_documents",
        sa.Column("scan_status", sa.String(length=20), server_default="PENDING", nullable=False),
    )
    op.add_column("job_documents", sa.Column("scan_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("job_documents", sa.Column("scan_message", sa.String(length=1024), nullable=True))
    op.add_column("job_documents", sa.Column("quarantined_s3_key", sa.String(length=512), nullable=True))

    # Backfill scan_status for existing rows based on legacy status
    op.execute(
        """
        UPDATE job_documents
        SET scan_status =
            CASE
                WHEN status = 'uploaded' THEN 'CLEAN'
                WHEN status = 'infected' THEN 'INFECTED'
                WHEN status = 'failed' THEN 'ERROR'
                ELSE 'PENDING'
            END
        """
    )


def downgrade() -> None:
    op.drop_column("job_documents", "quarantined_s3_key")
    op.drop_column("job_documents", "scan_message")
    op.drop_column("job_documents", "scan_checked_at")
    op.drop_column("job_documents", "scan_status")


