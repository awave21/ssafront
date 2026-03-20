"""Add WAPPI profile binding and phone channel types.

Revision ID: 0035
Revises: 0034
Create Date: 2026-03-03
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'channel_type' AND e.enumlabel = 'max'
            ) THEN
                ALTER TYPE channel_type ADD VALUE 'max';
            END IF;

            IF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON t.oid = e.enumtypid
                WHERE t.typname = 'channel_type' AND e.enumlabel = 'telegram_phone'
            ) THEN
                ALTER TYPE channel_type ADD VALUE 'telegram_phone';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE channels
        ADD COLUMN IF NOT EXISTS wappi_profile_id VARCHAR(120);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_channels_wappi_profile_id
        ON channels (wappi_profile_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_channels_wappi_profile_id;")
    op.execute("ALTER TABLE channels DROP COLUMN IF EXISTS wappi_profile_id;")
