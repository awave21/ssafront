"""Add tenant_llm_configs table for per-org OpenAI API keys

Revision ID: 0034
Revises: 0033
Create Date: 2026-02-23

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0034'
down_revision: Union[str, None] = '0033'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tenant_llm_configs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, server_default='openai'),
        sa.Column('encrypted_api_key', postgresql.JSONB, nullable=False),
        sa.Column('last4', sa.String(10), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_tenant_llm_configs_tenant_id', 'tenant_llm_configs', ['tenant_id'])
    op.create_unique_constraint('uq_tenant_llm_config_provider', 'tenant_llm_configs', ['tenant_id', 'provider'])


def downgrade() -> None:
    op.drop_constraint('uq_tenant_llm_config_provider', 'tenant_llm_configs', type_='unique')
    op.drop_index('ix_tenant_llm_configs_tenant_id', table_name='tenant_llm_configs')
    op.drop_table('tenant_llm_configs')
