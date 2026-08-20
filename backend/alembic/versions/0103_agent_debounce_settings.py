"""Add per-agent debounce (reply delay) settings.

Настройка задержки перед ответом на уровне агента, применяется ко всем каналам.
`debounce_enabled` — вкл/выкл, `debounce_delay_seconds` — окно склейки сообщений.

Revision ID: 0103
Revises: 0102
Create Date: 2026-08-11
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0103"
down_revision: Union[str, None] = "0102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "debounce_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "debounce_delay_seconds",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "debounce_delay_seconds")
    op.drop_column("agents", "debounce_enabled")
