"""Normalize agent analysis recommendation evidence payload

Revision ID: 0044
Revises: 0043
Create Date: 2026-03-16
"""
from __future__ import annotations

from typing import Any, Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0044"
down_revision: Union[str, None] = "0043"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize_evidence(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        dialog_id = item.get("dialog_id")
        if not isinstance(dialog_id, str):
            continue
        dialog_id = dialog_id.strip()
        if not dialog_id:
            continue

        row: dict[str, Any] = {"dialog_id": dialog_id}

        run_id = item.get("run_id")
        if isinstance(run_id, str):
            run_id = run_id.strip()
            if run_id:
                try:
                    row["run_id"] = str(UUID(run_id))
                except ValueError:
                    pass

        message_id = item.get("message_id")
        if isinstance(message_id, str):
            message_id = message_id.strip()
            if message_id:
                try:
                    row["message_id"] = str(UUID(message_id))
                except ValueError:
                    pass

        excerpt = item.get("excerpt")
        if isinstance(excerpt, str):
            row["excerpt"] = excerpt.strip()

        normalized.append(row)
    return normalized


def upgrade() -> None:
    bind = op.get_bind()
    recommendations_table = sa.table(
        "agent_analysis_recommendations",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("evidence", postgresql.JSONB(astext_type=sa.Text())),
    )

    rows = bind.execute(sa.select(recommendations_table.c.id, recommendations_table.c.evidence)).all()
    for row in rows:
        normalized = _normalize_evidence(row.evidence)
        if normalized == row.evidence:
            continue
        bind.execute(
            sa.update(recommendations_table)
            .where(recommendations_table.c.id == row.id)
            .values(evidence=normalized)
        )


def downgrade() -> None:
    # Data normalization is irreversible by design.
    pass
