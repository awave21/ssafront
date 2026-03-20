"""add webhook token for telegram channels

Revision ID: 0015_channel_webhook_token
Revises: 0014_agent_channels
Create Date: 2026-02-02
"""

from alembic import op

revision = "0015_channel_webhook_token"
down_revision = "0014_agent_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE channels
        ADD COLUMN IF NOT EXISTS telegram_webhook_token VARCHAR(120);
        """
    )

    op.execute(
        """
        UPDATE channels
        SET telegram_webhook_token = split_part(telegram_webhook_endpoint, '/', -1)
        WHERE telegram_webhook_token IS NULL
          AND telegram_webhook_endpoint IS NOT NULL
          AND telegram_webhook_endpoint <> '';
        """
    )

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_channels_telegram_webhook_token "
        "ON channels (telegram_webhook_token);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_channels_telegram_webhook_token;")
    op.execute("ALTER TABLE channels DROP COLUMN IF EXISTS telegram_webhook_token;")
