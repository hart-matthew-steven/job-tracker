"""ensure job_applications owned by user

Revision ID: 4306ca53ea6c
Revises: 6b9de2f768ae
Create Date: 2025-12-16 18:30:44.486932

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = '4306ca53ea6c'
down_revision: Union[str, Sequence[str], None] = '6b9de2f768ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
