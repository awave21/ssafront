"""Add runtime_bridges_mode to agents.

Controls whether tool-orchestration bridge texts are auto-injected into the
system prompt by the runtime ("auto", default) or left entirely to the user
("manual" — user writes all tool-call instructions in their own system prompt).

Revision ID: 0085
Revises: 0084
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0085"
down_revision: Union[str, None] = "0083"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Существующие агенты получают "auto" для обратной совместимости —
    # они работали с авто-инжекцией и ожидают её.
    # Новые агенты создаются с "manual" (default в модели) — пользователь
    # сам пишет инструкции в системном промпте.
    op.add_column(
        "agents",
        sa.Column(
            "runtime_bridges_mode",
            sa.String(20),
            nullable=False,
            server_default="auto",  # backward compat для существующих агентов
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "runtime_bridges_mode")
