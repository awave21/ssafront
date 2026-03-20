"""Add prompt training sessions and feedback tables

Revision ID: 0033
Revises: 0032
Create Date: 2026-02-21

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0033'
down_revision: Union[str, None] = '0032'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prompt_training_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('agent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('base_prompt_version', sa.Integer(), nullable=False),
        sa.Column('generated_prompt', sa.Text(), nullable=True),
        sa.Column('generated_prompt_reasoning', sa.Text(), nullable=True),
        sa.Column('generated_version_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('system_prompt_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('feedback_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('meta_model', sa.String(200), nullable=False, server_default='openai:gpt-4o'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_prompt_training_sessions_agent_id', 'prompt_training_sessions', ['agent_id'])
    op.create_index('ix_prompt_training_sessions_tenant_id', 'prompt_training_sessions', ['tenant_id'])
    op.create_index('ix_prompt_training_sessions_tenant_status', 'prompt_training_sessions', ['tenant_id', 'status'])

    op.create_table(
        'prompt_training_feedback',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('training_session_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompt_training_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('runs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('feedback_type', sa.String(20), nullable=False),
        sa.Column('user_message', sa.Text(), nullable=True),
        sa.Column('agent_response', sa.Text(), nullable=True),
        sa.Column('correction_text', sa.Text(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_prompt_training_feedback_session_id', 'prompt_training_feedback', ['training_session_id'])
    op.create_index('ix_prompt_training_feedback_tenant_id', 'prompt_training_feedback', ['tenant_id'])


def downgrade() -> None:
    op.drop_index('ix_prompt_training_feedback_tenant_id', table_name='prompt_training_feedback')
    op.drop_index('ix_prompt_training_feedback_session_id', table_name='prompt_training_feedback')
    op.drop_table('prompt_training_feedback')

    op.drop_index('ix_prompt_training_sessions_tenant_status', table_name='prompt_training_sessions')
    op.drop_index('ix_prompt_training_sessions_tenant_id', table_name='prompt_training_sessions')
    op.drop_index('ix_prompt_training_sessions_agent_id', table_name='prompt_training_sessions')
    op.drop_table('prompt_training_sessions')
