"""Add table_find and table_write function post-action types.

Пользовательские таблицы («База знаний → Таблицы») до этого были полностью
изолированы от агента: ни прочитать, ни записать из правила было нельзя.
Действия работают поверх той же модели, что и таблицы в интерфейсе.

Revision ID: 0107
Revises: 0106
Create Date: 2026-08-20
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0107"
down_revision: Union[str, None] = "0106"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE function_post_action_type ADD VALUE IF NOT EXISTS 'table_find'")
    op.execute("ALTER TYPE function_post_action_type ADD VALUE IF NOT EXISTS 'table_write'")


def downgrade() -> None:
    # PostgreSQL не умеет DROP VALUE у enum — значения остаются в типе.
    pass
