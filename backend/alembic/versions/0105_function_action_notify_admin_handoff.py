"""Add notify_admin and handoff_to_operator function post-action types.

До этого уведомление администратору было побочным эффектом, намертво привязанным
к `behavior_after_execution=pause` (см. function_rules_runtime), а «передача
оператору» вообще не существовала как понятие — её приходилось собирать вручную
из паузы плюс настроек агента. Оба сценария теперь доступны как обычные действия
правила, которые можно поставить в любом порядке и с любым `on_status`.

Revision ID: 0105
Revises: 0104
Create Date: 2026-08-20
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0105"
down_revision: Union[str, None] = "0104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE function_post_action_type ADD VALUE IF NOT EXISTS 'notify_admin'"
    )
    op.execute(
        "ALTER TYPE function_post_action_type ADD VALUE IF NOT EXISTS 'handoff_to_operator'"
    )


def downgrade() -> None:
    # PostgreSQL не умеет DROP VALUE у enum — значения остаются в типе.
    # Тот же подход, что в 0096 (web_widget) и 0102 (jivo).
    pass
