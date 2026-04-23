"""Add last_tactic_style JSONB to session_script_contexts.

Stores the communication style of the last matched expert tactic so it can be
pre-baked into the system prompt on subsequent turns — making style instructions
a "law" rather than an optional tool-result suggestion.

Revision ID: 0083
Revises: 0082
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0083"
down_revision: Union[str, None] = "0082"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "session_script_contexts",
        sa.Column("last_tactic_style", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("session_script_contexts", "last_tactic_style")
