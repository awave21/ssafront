"""Add webhook scope for tools.

Revision ID: 0038
Revises: 0037
Create Date: 2026-03-04
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tool_webhook_scope') THEN
                CREATE TYPE tool_webhook_scope AS ENUM ('tool', 'function_only', 'both');
            END IF;
        END $$;
        """
    )

    op.add_column(
        "tools",
        sa.Column(
            "webhook_scope",
            sa.Enum("tool", "function_only", "both", name="tool_webhook_scope"),
            nullable=False,
            server_default="tool",
        ),
    )


def downgrade() -> None:
    op.drop_column("tools", "webhook_scope")
    sa.Enum(name="tool_webhook_scope").drop(op.get_bind(), checkfirst=True)
