"""Add SQNS clients storage table

Revision ID: 0049_sqns_clients_sync_storage
Revises: 0048
Create Date: 2026-03-17
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0049_sqns_clients_sync_storage"
down_revision: Union[str, None] = "0048"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sqns_clients (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
            external_id INTEGER NOT NULL,
            sex INTEGER,
            client_type VARCHAR(120),
            visits_count INTEGER,
            total_arrival NUMERIC(12, 2),
            tags JSONB,
            pii_data JSONB,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ,
            CONSTRAINT uq_sqns_clients_agent_external UNIQUE (agent_id, external_id)
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_clients_agent_id ON sqns_clients (agent_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_clients_client_type ON sqns_clients (client_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sqns_clients_external_id ON sqns_clients (external_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sqns_clients CASCADE;")
