"""Add local authorization flag for phone channels.

Revision ID: 0036
Revises: 0035
Create Date: 2026-03-03
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE channels
        ADD COLUMN IF NOT EXISTS phone_is_authorized BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE channels DROP COLUMN IF EXISTS phone_is_authorized;")
