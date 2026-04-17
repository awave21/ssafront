"""Add manager_pause_minutes to agents and last_manager_message_at to dialog_states

Revision ID: 0022_manager_pause
Revises: 0021_dialog_states
Create Date: 2026-02-08

"""

from alembic import op
import sqlalchemy as sa

revision = "0022_manager_pause"
down_revision = "0021_dialog_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # manager_pause_minutes — глобальная настройка агента
    op.add_column(
        "agents",
        sa.Column(
            "manager_pause_minutes",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )
    # last_manager_message_at — per-dialog (время последнего сообщения менеджера)
    op.add_column(
        "dialog_states",
        sa.Column(
            "last_manager_message_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Раньше здесь был drop_column в try/except — при отсутствии столбца Postgres
    # помечал транзакцию как aborted, и обновление alembic_version ломалось.
    op.execute(
        sa.text(
            "ALTER TABLE dialog_states DROP COLUMN IF EXISTS manager_pause_minutes"
        )
    )


def downgrade() -> None:
    op.drop_column("dialog_states", "last_manager_message_at")
    op.drop_column("agents", "manager_pause_minutes")
