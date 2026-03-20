"""agent per-agent runtime config fields

Revision ID: 0051
Revises: 0050
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Максимум tool-вызовов в одном запуске агента (per-agent override).
    # NULL → используется глобальный RUNTIME_TOOL_CALLS_LIMIT.
    op.add_column(
        "agents",
        sa.Column("max_tool_calls", sa.Integer(), nullable=True),
    )

    # Максимум элементов базы знаний, передаваемых в контекст (per-agent override).
    # NULL → используется глобальный DIRECT_QUESTIONS_ROUTER_MAX_ITEMS.
    op.add_column(
        "agents",
        sa.Column("direct_questions_limit", sa.Integer(), nullable=True),
    )

    # Кастомный промпт для суммаризатора истории диалога.
    # NULL → автоматически генерируется из system_prompt агента.
    op.add_column(
        "agents",
        sa.Column("summary_prompt", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "summary_prompt")
    op.drop_column("agents", "direct_questions_limit")
    op.drop_column("agents", "max_tool_calls")
