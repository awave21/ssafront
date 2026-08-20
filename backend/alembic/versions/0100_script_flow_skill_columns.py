"""Skill-layer columns on script_flows.

Добавляет две колонки на script_flows для модели «навык = продолжение эксперта»:
  - service_external_ids JSONB — явная связь потока↔услуга (список внешних
    id услуг из SQNS). Раньше связь жила только в flow_metadata["service_ids"];
    эта колонка делает её первичной и редактируемой из UI «Навыки».
  - skill_doc JSONB — дистиллированная структура навыка (objections/phrases с
    уровнями дословности/gaps/…), производная от compiled_text. Заполняется при
    публикации потока reasoning-моделью (строго extractive).

Revision ID: 0100
Revises: 0099
Create Date: 2026-07-11
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0100"
down_revision: Union[str, None] = "0099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "script_flows",
        sa.Column(
            "service_external_ids",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
    )
    op.add_column(
        "script_flows",
        sa.Column("skill_doc", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("script_flows", "skill_doc")
    op.drop_column("script_flows", "service_external_ids")
