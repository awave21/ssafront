"""Seed or reactivate OpenAI ModelPricing rows (UI model picker + billing).

Revision ID: 0082
Revises: 0081
Create Date: 2026-04-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0082"
down_revision: Union[str, None] = "0081"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Placeholder per-1M-token pricing (USD / RUB); aligns with MODEL_PRESETS in model_pricing router.
# RUB uses ~90× USD like migration 0070; adjust via admin/API as needed.
_OPENAI_MODELS: list[tuple[str, str, str, str, str, str]] = [
    ("gpt-5.2", "GPT-5.2 (Лучшая для кодинга и агентов)", "5.0", "15.0", "450.0", "1350.0"),
    ("gpt-5.2-pro", "GPT-5.2 Pro (Умнее и точнее)", "15.0", "120.0", "1350.0", "10800.0"),
    ("gpt-5-mini", "GPT-5 Mini (Быстрая, экономная)", "0.25", "2.0", "22.5", "180.0"),
    ("gpt-5-nano", "GPT-5 Nano (Самая быстрая)", "0.05", "0.40", "4.5", "36.0"),
    ("gpt-5.1", "GPT-5.1 (Предыдущее поколение)", "3.0", "12.0", "270.0", "1080.0"),
    ("gpt-5", "GPT-5 (Стабильная)", "2.5", "10.0", "225.0", "900.0"),
    ("gpt-4.1", "GPT-4.1 (Умная, без рассуждений)", "2.0", "8.0", "180.0", "720.0"),
    ("gpt-4.1-mini", "GPT-4.1 Mini (Быстрая)", "0.40", "1.60", "36.0", "144.0"),
    ("gpt-4.1-nano", "GPT-4.1 Nano (Экономная)", "0.10", "0.40", "9.0", "36.0"),
    ("gpt-4o", "GPT-4o (Мультимодальная)", "2.50", "10.0", "225.0", "900.0"),
    ("gpt-4o-mini", "GPT-4o Mini (Быстрая, дешевая)", "0.15", "0.60", "13.5", "54.0"),
    ("o3", "o3 (Сложные задачи)", "10.0", "40.0", "900.0", "3600.0"),
    ("o3-pro", "o3 Pro (Больше вычислений)", "20.0", "80.0", "1800.0", "7200.0"),
    ("o4-mini", "o4 Mini (Быстрые рассуждения)", "1.10", "4.40", "99.0", "396.0"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for model_name, display_name, in_usd, out_usd, in_rub, out_rub in _OPENAI_MODELS:
        conn.execute(
            sa.text(
                """
                INSERT INTO model_pricing (
                    id, provider, model_name, display_name, is_active,
                    input_usd, output_usd, input_rub, output_rub, created_at
                )
                VALUES (
                    gen_random_uuid(), 'openai', :model_name, :display_name, true,
                    CAST(:in_usd AS NUMERIC(18, 8)),
                    CAST(:out_usd AS NUMERIC(18, 8)),
                    CAST(:in_rub AS NUMERIC(18, 8)),
                    CAST(:out_rub AS NUMERIC(18, 8)),
                    now()
                )
                ON CONFLICT (provider, model_name) DO UPDATE SET
                    is_active = true,
                    display_name = EXCLUDED.display_name,
                    input_usd = EXCLUDED.input_usd,
                    output_usd = EXCLUDED.output_usd,
                    input_rub = EXCLUDED.input_rub,
                    output_rub = EXCLUDED.output_rub,
                    updated_at = now()
                """
            ),
            {
                "model_name": model_name,
                "display_name": display_name,
                "in_usd": in_usd,
                "out_usd": out_usd,
                "in_rub": in_rub,
                "out_rub": out_rub,
            },
        )


def downgrade() -> None:
    names = [m[0] for m in _OPENAI_MODELS]
    in_list = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    op.execute(
        sa.text(
            f"DELETE FROM model_pricing WHERE provider = 'openai' AND model_name IN ({in_list})"
        )
    )
