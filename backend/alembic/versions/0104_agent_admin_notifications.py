"""Add per-agent admin Telegram notification settings.

Позволяет отправлять уведомление менеджеру в Telegram при срабатывании правила
с behavior_after_execution=pause. Хранит токен бота и chat_id менеджера на уровне
агента. Токен хранится в открытом виде (MVP), в проде стоит перейти на шифрование
через `credentials_encryption_key` — см. TODO в services/ops_alerts.py.

Revision ID: 0104
Revises: 0103
Create Date: 2026-08-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0104"
down_revision: Union[str, None] = "0103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "admin_notification_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "admin_notification_bot_token",
            sa.String(length=200),
            nullable=True,
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "admin_notification_chat_id",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "admin_notification_chat_id")
    op.drop_column("agents", "admin_notification_bot_token")
    op.drop_column("agents", "admin_notification_enabled")
