"""Add HTTP enhancements to tools: http_method, custom_headers, response_transform, parameter_mapping

Revision ID: 0030_tool_http_enhancements
Revises: 0029_run_token_usage_detail_tokens
Create Date: 2026-02-10 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0030_tool_http_enhancements'
down_revision: Union[str, None] = '0029_run_usage_detail_toks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add http_method column (default POST for backward compatibility)
    op.add_column('tools', sa.Column('http_method', sa.String(length=10), nullable=False, server_default='POST'))
    
    # Add custom_headers column (JSONB for static headers like Content-Type, X-Custom, etc.)
    op.add_column('tools', sa.Column('custom_headers', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add response_transform column (JSONB for flexible filter configuration)
    op.add_column('tools', sa.Column('response_transform', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Add parameter_mapping column (JSONB for path/query/body/header mapping)
    op.add_column('tools', sa.Column('parameter_mapping', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('tools', 'parameter_mapping')
    op.drop_column('tools', 'response_transform')
    op.drop_column('tools', 'custom_headers')
    op.drop_column('tools', 'http_method')
