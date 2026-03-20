"""add channels for agents

Revision ID: 0014_agent_channels
Revises: 0013_agent_sqns_warning
Create Date: 2026-02-02
"""

from alembic import op

revision = "0014_agent_channels"
down_revision = "0013_agent_sqns_warning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE channel_type AS ENUM ('telegram', 'whatsapp');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id UUID PRIMARY KEY,
            type channel_type NOT NULL,
            telegram_bot_token VARCHAR(200),
            telegram_webhook_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            telegram_webhook_endpoint VARCHAR(500),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_channels (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            channel_id UUID NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_agent_channels_agent_channel UNIQUE (agent_id, channel_id)
        );
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_channels_type ON channels (type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_channels_is_deleted ON channels (is_deleted);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_channels_agent_id ON agent_channels (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_agent_channels_channel_id ON agent_channels (channel_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_channels CASCADE;")
    op.execute("DROP TABLE IF EXISTS channels CASCADE;")
    op.execute("DROP TYPE IF EXISTS channel_type;")
