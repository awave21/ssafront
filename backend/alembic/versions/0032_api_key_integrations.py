"""Add integration fields to api_keys

Revision ID: 0032
Revises: 0031_agent_timezone
Create Date: 2026-02-19

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0032'
down_revision: Union[str, None] = '0031_agent_timezone'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns (nullable first, will add NOT NULL after data migration)
    op.add_column('api_keys', sa.Column('name', sa.String(100), nullable=True, server_default=''))
    op.add_column('api_keys', sa.Column('agent_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('api_keys', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('api_keys', sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('api_keys', sa.Column('daily_limit', sa.Integer(), nullable=True))

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_api_keys_agent_id',
        'api_keys', 'agents',
        ['agent_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add index on agent_id
    op.create_index('ix_api_keys_agent_id', 'api_keys', ['agent_id'])

    # Data migration: set name for existing keys
    # Using raw SQL to update existing rows
    op.execute("UPDATE api_keys SET name = 'API Key ' || LEFT(id::text, 8) WHERE name = '' OR name IS NULL")

    # Now set NOT NULL
    op.alter_column('api_keys', 'name', nullable=False)


def downgrade() -> None:
    op.drop_index('ix_api_keys_agent_id', table_name='api_keys')
    op.drop_constraint('fk_api_keys_agent_id', table_name='api_keys')
    op.drop_column('api_keys', 'daily_limit')
    op.drop_column('api_keys', 'total_calls')
    op.drop_column('api_keys', 'expires_at')
    op.drop_column('api_keys', 'agent_id')
    op.drop_column('api_keys', 'name')
