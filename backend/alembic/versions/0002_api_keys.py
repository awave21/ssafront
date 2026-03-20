"""add api_keys

Revision ID: 0002_api_keys
Revises: 0001_initial
Create Date: 2026-01-20
"""

from alembic import op


revision = "0002_api_keys"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        id UUID PRIMARY KEY,
        tenant_id UUID NOT NULL,
        user_id UUID NOT NULL,
        key_hash VARCHAR(128) NOT NULL,
        last4 VARCHAR(4) NOT NULL,
        scopes JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ,
        revoked_at TIMESTAMPTZ,
        last_used_at TIMESTAMPTZ
    );
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_api_keys_hash ON api_keys (key_hash);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys (tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_user_id ON api_keys (user_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_keys")
