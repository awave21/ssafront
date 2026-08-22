"""Add per-dialog variables storage and set_variable action type.

Переменные диалога — недостающее звено между действиями правил: до этого
augment_prompt жил ровно один прогон агента и исчезал, а сохранить значение
и переиспользовать его дальше по разговору было негде. Кладём в dialog_states,
где уже есть уникальный ключ (session_id, agent_id).

Revision ID: 0106
Revises: 0105
Create Date: 2026-08-20
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0106"
down_revision: Union[str, None] = "0105"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dialog_states",
        sa.Column(
            "variables",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.execute(
        "ALTER TYPE function_post_action_type ADD VALUE IF NOT EXISTS 'set_variable'"
    )


def downgrade() -> None:
    op.drop_column("dialog_states", "variables")
    # Значение enum не удаляем — DROP VALUE в PostgreSQL не поддерживается.
