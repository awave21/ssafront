"""Add jivo channel type and provider fields.

Канал Jivo (Bot API): мы — бот-провайдер. Токен генерим мы (inbound-аутентификация
+ сегмент в URL ответа), `provider_id`/`reply_base_url` вводит клиент из кабинета Jivo.
Исходящий ответ уходит на {reply_base_url}/{provider_id}/{token}.

Revision ID: 0102
Revises: 0101
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0102"
down_revision: Union[str, None] = "0101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE channel_type ADD VALUE IF NOT EXISTS 'jivo'")

    op.add_column("channels", sa.Column("jivo_provider_token", sa.String(200), nullable=True))
    op.add_column("channels", sa.Column("jivo_provider_id", sa.String(120), nullable=True))
    op.add_column("channels", sa.Column("jivo_reply_base_url", sa.String(500), nullable=True))

    op.create_unique_constraint(
        "uq_channels_jivo_provider_token", "channels", ["jivo_provider_token"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_channels_jivo_provider_token", "channels", type_="unique")
    op.drop_column("channels", "jivo_reply_base_url")
    op.drop_column("channels", "jivo_provider_id")
    op.drop_column("channels", "jivo_provider_token")
    # Значение enum 'jivo' не удаляем — DROP VALUE в PostgreSQL не поддерживается
    # (аналогично тому, как 0096 не откатывает 'web_widget').
