"""Seed ModelPricing rows for Anthropic Claude (active-models + billing).

Revision ID: 0070
Revises: 0069
Create Date: 2026-04-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0070"
down_revision: Union[str, None] = "0069"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Placeholder per-1M-token pricing (USD / RUB); adjust in admin as needed.
_ANTHROPIC_MODELS: list[tuple[str, str, str, str, str, str]] = [
    ("claude-sonnet-4-5", "Claude Sonnet 4.5", "3.0", "15.0", "270.0", "1350.0"),
    ("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", "3.0", "15.0", "270.0", "1350.0"),
    ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", "1.0", "5.0", "90.0", "450.0"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for model_name, display_name, in_usd, out_usd, in_rub, out_rub in _ANTHROPIC_MODELS:
        conn.execute(
            sa.text(
                """
                INSERT INTO model_pricing (
                    id, provider, model_name, display_name, is_active,
                    input_usd, output_usd, input_rub, output_rub, created_at
                )
                VALUES (
                    gen_random_uuid(), 'anthropic', :model_name, :display_name, true,
                    CAST(:in_usd AS NUMERIC(18, 8)),
                    CAST(:out_usd AS NUMERIC(18, 8)),
                    CAST(:in_rub AS NUMERIC(18, 8)),
                    CAST(:out_rub AS NUMERIC(18, 8)),
                    now()
                )
                ON CONFLICT (provider, model_name) DO NOTHING
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
    names = [m[0] for m in _ANTHROPIC_MODELS]
    in_list = ",".join("'" + n.replace("'", "''") + "'" for n in names)
    op.execute(sa.text(f"DELETE FROM model_pricing WHERE provider = 'anthropic' AND model_name IN ({in_list})"))
