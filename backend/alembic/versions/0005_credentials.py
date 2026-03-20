"""add credentials and binding credential link

Revision ID: 0005_credentials
Revises: 0004_tool_auth_types
Create Date: 2026-01-21
"""

from alembic import op

revision = "0005_credentials"
down_revision = "0004_tool_auth_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS credentials (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL,
            name VARCHAR(200) NOT NULL,
            auth_type VARCHAR(50) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_credentials_tenant_name ON credentials (tenant_id, name);"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_credentials_tenant_id ON credentials (tenant_id);")

    op.execute("ALTER TABLE agent_tool_bindings ADD COLUMN IF NOT EXISTS credential_id UUID;")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'fk_agent_tool_bindings_credential_id'
            ) THEN
                ALTER TABLE agent_tool_bindings
                ADD CONSTRAINT fk_agent_tool_bindings_credential_id
                FOREIGN KEY (credential_id) REFERENCES credentials(id)
                ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_agent_tool_bindings_credential_id ON agent_tool_bindings (credential_id);"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agent_tool_bindings DROP CONSTRAINT IF EXISTS fk_agent_tool_bindings_credential_id;")
    op.execute("ALTER TABLE agent_tool_bindings DROP COLUMN IF EXISTS credential_id;")
    op.execute("DROP TABLE IF EXISTS credentials;")
