"""Ensure root-level schema_version on stored flow_definition JSON.

Revision ID: 0080
Revises: 0079
Create Date: 2026-04-18
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0080"
down_revision: Union[str, None] = "0079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE script_flows
            SET flow_definition = flow_definition || '{"schema_version": 1}'::jsonb
            WHERE COALESCE((flow_definition->>'schema_version')::text, '') = '';
            """
        )
    )


def downgrade() -> None:
    pass
