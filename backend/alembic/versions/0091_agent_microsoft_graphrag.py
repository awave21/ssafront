"""Microsoft GraphRAG: флаги агента и время последней индексации.

Revision ID: 0091
Revises: 0090
Create Date: 2026-04-26
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0091"
down_revision: Union[str, None] = "0090"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS: база могла уже получить колонки при прогоне той же ревизии с другой копией кода.
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS microsoft_graphrag_enabled BOOLEAN "
        "NOT NULL DEFAULT false;"
    )
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS microsoft_graphrag_workspace_slug VARCHAR(120);"
    )
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS microsoft_graphrag_tool_description TEXT;"
    )
    op.execute(
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS microsoft_graphrag_last_indexed_at "
        "TIMESTAMP WITH TIME ZONE;"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS microsoft_graphrag_last_indexed_at;")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS microsoft_graphrag_tool_description;")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS microsoft_graphrag_workspace_slug;")
    op.execute("ALTER TABLE agents DROP COLUMN IF EXISTS microsoft_graphrag_enabled;")
