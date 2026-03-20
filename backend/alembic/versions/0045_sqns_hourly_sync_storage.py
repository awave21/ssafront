"""Add SQNS hourly sync storage tables

Revision ID: 0045
Revises: 0044
Create Date: 2026-03-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0045"
down_revision: Union[str, None] = "0044"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE agents
        ADD COLUMN IF NOT EXISTS sqns_last_activity_at TIMESTAMPTZ;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_commodities (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id INTEGER NOT NULL,
            title VARCHAR(500) NOT NULL,
            description TEXT,
            category VARCHAR(200),
            price NUMERIC(10, 2),
            article VARCHAR(200),
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_commodities_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_commodities_agent_id ON sqns_commodities (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_commodities_category ON sqns_commodities (category);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_commodities_article ON sqns_commodities (article);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_employees (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id INTEGER NOT NULL,
            firstname VARCHAR(120),
            lastname VARCHAR(120),
            patronymic VARCHAR(120),
            full_name VARCHAR(400) NOT NULL,
            image VARCHAR(500),
            position VARCHAR(200),
            rating VARCHAR(50),
            updated_at_external TIMESTAMPTZ,
            is_fired BOOLEAN NOT NULL DEFAULT FALSE,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_employees_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_employees_agent_id ON sqns_employees (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_employees_full_name ON sqns_employees (full_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_employees_position ON sqns_employees (position);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_employees_is_fired ON sqns_employees (is_fired);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_employees_is_deleted ON sqns_employees (is_deleted);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_visits (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id INTEGER NOT NULL,
            resource_external_id INTEGER,
            client_external_id INTEGER,
            visit_datetime TIMESTAMPTZ,
            attendance INTEGER,
            deleted BOOLEAN NOT NULL DEFAULT FALSE,
            online BOOLEAN NOT NULL DEFAULT FALSE,
            total_price NUMERIC(12, 2),
            total_cost NUMERIC(12, 2),
            comment TEXT,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_visits_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_visits_agent_id ON sqns_visits (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_visits_resource_external_id ON sqns_visits (resource_external_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_visits_client_external_id ON sqns_visits (client_external_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_visits_visit_datetime ON sqns_visits (visit_datetime);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_visits_attendance ON sqns_visits (attendance);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_visits_deleted ON sqns_visits (deleted);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_payments (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id VARCHAR(200) NOT NULL,
            payment_date TIMESTAMPTZ,
            payment_method VARCHAR(120),
            payment_type_id VARCHAR(120),
            payment_type_handle VARCHAR(120),
            payment_type_name VARCHAR(200),
            organization_external_id VARCHAR(120),
            client_external_id VARCHAR(120),
            visit_external_id VARCHAR(120),
            amount NUMERIC(12, 2),
            comment TEXT,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_payments_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_payments_agent_id ON sqns_payments (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_payments_payment_date ON sqns_payments (payment_date);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_payments_payment_method ON sqns_payments (payment_method);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_payments_client_external_id ON sqns_payments (client_external_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_payments_visit_external_id ON sqns_payments (visit_external_id);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_sync_cursor (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            entity VARCHAR(50) NOT NULL,
            modificate_value BIGINT,
            date_from DATE,
            date_till DATE,
            last_success_at TIMESTAMPTZ,
            state JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_sync_cursor_agent_entity UNIQUE (agent_id, entity)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_sync_cursor_agent_id ON sqns_sync_cursor (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_sync_cursor_entity ON sqns_sync_cursor (entity);")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_sync_runs (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            trigger VARCHAR(30) NOT NULL DEFAULT 'hourly',
            status VARCHAR(30) NOT NULL DEFAULT 'running',
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ,
            duration_ms INTEGER,
            entities JSONB,
            details JSONB,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_sync_runs_agent_id ON sqns_sync_runs (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_sync_runs_trigger ON sqns_sync_runs (trigger);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_sync_runs_status ON sqns_sync_runs (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_sync_runs_started_at ON sqns_sync_runs (started_at);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sqns_sync_runs CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_sync_cursor CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_payments CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_visits CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_employees CASCADE;")
    op.execute("DROP TABLE IF EXISTS sqns_commodities CASCADE;")
    op.execute(
        """
        ALTER TABLE agents
        DROP COLUMN IF EXISTS sqns_last_activity_at;
        """
    )
