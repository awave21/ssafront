"""add users and tenants

Revision ID: 0003_users_tenants
Revises: 0002_api_keys
Create Date: 2026-01-21
"""

from alembic import op

revision = "0003_users_tenants"
down_revision = "0002_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            id UUID PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            plan VARCHAR(50) NOT NULL DEFAULT 'free',
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenants_name ON tenants (name);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(320) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(200),
            role VARCHAR(50) NOT NULL DEFAULT 'owner',
            scopes JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_login_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_tenant_id ON users (tenant_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS tenants")
