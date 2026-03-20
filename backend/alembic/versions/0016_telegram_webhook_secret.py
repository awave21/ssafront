"""Добавить telegram_webhook_secret для Telegram-каналов

Revision ID: 0016_telegram_webhook_secret
Revises: 0015_channel_webhook_token
Create Date: 2026-02-02
"""

from alembic import op

revision = "0016_telegram_webhook_secret"
down_revision = "0015_channel_webhook_token"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE channels
        ADD COLUMN IF NOT EXISTS telegram_webhook_secret VARCHAR(120);
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE channels DROP COLUMN IF EXISTS telegram_webhook_secret;")
