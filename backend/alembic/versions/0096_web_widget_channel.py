"""Add web_widget channel type and widget fields.

Revision ID: 0096
Revises: 0095
Create Date: 2026-05-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0096"
down_revision: Union[str, None] = "0095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE channel_type ADD VALUE IF NOT EXISTS 'web_widget'")

    op.add_column(
        "channels",
        sa.Column("widget_api_key_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("api_keys.id", ondelete="SET NULL"), nullable=True),
    )
    op.add_column("channels", sa.Column("widget_api_key_last4", sa.String(4), nullable=True))
    op.add_column("channels", sa.Column("widget_allowed_origins", postgresql.JSONB(), nullable=True))
    op.add_column("channels", sa.Column("widget_settings", postgresql.JSONB(), nullable=True))

    op.create_index("ix_channels_widget_api_key_id", "channels", ["widget_api_key_id"])


def downgrade() -> None:
    op.drop_index("ix_channels_widget_api_key_id", table_name="channels")
    op.drop_column("channels", "widget_settings")
    op.drop_column("channels", "widget_allowed_origins")
    op.drop_column("channels", "widget_api_key_last4")
    op.drop_column("channels", "widget_api_key_id")
