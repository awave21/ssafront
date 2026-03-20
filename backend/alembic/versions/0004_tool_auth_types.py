"""expand tool auth types

Revision ID: 0004_tool_auth_types
Revises: 0003_users_tenants
Create Date: 2026-01-21
"""

from alembic import op

revision = "0004_tool_auth_types"
down_revision = "0003_users_tenants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tool_auth_type ADD VALUE IF NOT EXISTS 'bearer_token'")
        op.execute("ALTER TYPE tool_auth_type ADD VALUE IF NOT EXISTS 'basic_auth'")
        op.execute("ALTER TYPE tool_auth_type ADD VALUE IF NOT EXISTS 'custom_header'")
        op.execute("ALTER TYPE tool_auth_type ADD VALUE IF NOT EXISTS 'query_param'")


def downgrade() -> None:
    # Enum value removal is not supported in PostgreSQL; no-op downgrade.
    pass
