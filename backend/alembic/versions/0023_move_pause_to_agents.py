"""Move manager_pause_minutes from dialog_states to agents (global setting)

Revision ID: 0023_move_pause_to_agents
Revises: 0022_manager_pause
Create Date: 2026-02-08

"""

from alembic import op
import sqlalchemy as sa

revision = "0023_move_pause_to_agents"
down_revision = "0022_manager_pause"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Добавляем manager_pause_minutes в agents (глобальная настройка)
    op.add_column(
        "agents",
        sa.Column(
            "manager_pause_minutes",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    # Удаляем manager_pause_minutes из dialog_states (больше не per-dialog)
    op.drop_column("dialog_states", "manager_pause_minutes")


def downgrade() -> None:
    # Возвращаем manager_pause_minutes в dialog_states
    op.add_column(
        "dialog_states",
        sa.Column(
            "manager_pause_minutes",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    # Удаляем из agents
    op.drop_column("agents", "manager_pause_minutes")
