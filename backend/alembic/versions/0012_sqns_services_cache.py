"""add sqns services cache tables

Revision ID: 0012_sqns_services_cache
Revises: 0011_refresh_tokens
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_sqns_services_cache"
down_revision = "0011_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pg_trgm extension for ILIKE search performance
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # Create sqns_resources table (specialists/doctors cache)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_resources (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id INTEGER NOT NULL,
            name VARCHAR(300) NOT NULL,
            specialization VARCHAR(200),
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_resources_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )

    # Create sqns_services table (services cache)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_services (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id INTEGER NOT NULL,
            name VARCHAR(500) NOT NULL,
            category VARCHAR(200),
            price NUMERIC(10, 2),
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            priority INTEGER NOT NULL DEFAULT 0,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_services_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )

    # Create sqns_service_resources table (many-to-many relationship)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_service_resources (
            id UUID PRIMARY KEY,
            service_id UUID NOT NULL REFERENCES sqns_services(id) ON DELETE CASCADE,
            resource_id UUID NOT NULL REFERENCES sqns_resources(id) ON DELETE CASCADE,
            duration_seconds INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_service_resources UNIQUE (service_id, resource_id)
        );
        """
    )

    # Create sqns_service_categories table (category settings)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_service_categories (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_categories_agent_name UNIQUE (agent_id, name)
        );
        """
    )

    # Create indexes for sqns_resources
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_resources_agent_id ON sqns_resources (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_resources_external_id ON sqns_resources (external_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_resources_is_active ON sqns_resources (is_active);")
    # GIN index for ILIKE search on name using trigrams
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_resources_name_trgm ON sqns_resources USING gin (name gin_trgm_ops);"
    )

    # Create indexes for sqns_services
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_services_agent_id ON sqns_services (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_services_external_id ON sqns_services (external_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_services_category ON sqns_services (category);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_services_is_enabled ON sqns_services (is_enabled);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_services_priority ON sqns_services (priority);")
    # GIN indexes for ILIKE search on name and description using trigrams
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_services_name_trgm ON sqns_services USING gin (name gin_trgm_ops);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_services_description_trgm ON sqns_services USING gin (description gin_trgm_ops);"
    )

    # Create indexes for sqns_service_resources
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_service_resources_service_id ON sqns_service_resources (service_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_service_resources_resource_id ON sqns_service_resources (resource_id);"
    )

    # Create indexes for sqns_service_categories
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_service_categories_agent_id ON sqns_service_categories (agent_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sqns_service_categories_is_enabled ON sqns_service_categories (is_enabled);"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sqns_service_resources CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_service_categories CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_services CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_resources CASCADE;")
    # Note: We don't drop pg_trgm extension as it might be used by other tables
