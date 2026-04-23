"""Wave 7: migrate stored flow_definition to schema_version 2 (per-type node.data).

Revision ID: 0081
Revises: 0080
Create Date: 2026-04-18
"""

from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0081"
down_revision: Union[str, None] = "0080"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from app.services.script_flow_v2_migrate import (
        flow_has_invalid_goto,
        migrate_flow_definition_to_v2,
    )

    rows = conn.execute(
        sa.text(
            "SELECT id, flow_definition, flow_metadata, flow_status FROM script_flows",
        ),
    ).mappings().all()

    for row in rows:
        fd = row["flow_definition"]
        if not isinstance(fd, dict):
            fd = {}
        if fd.get("schema_version") == 2:
            continue
        meta = row["flow_metadata"]
        if not isinstance(meta, dict):
            meta = {}
        new_fd, _audit = migrate_flow_definition_to_v2(fd, flow_metadata=meta)
        status = row["flow_status"]
        if flow_has_invalid_goto(new_fd) and status == "published":
            status = "draft"
        conn.execute(
            sa.text(
                "UPDATE script_flows SET flow_definition = CAST(:fd AS jsonb), "
                "flow_status = :st WHERE id = :id",
            ),
            {"fd": json.dumps(new_fd), "st": status, "id": row["id"]},
        )


def downgrade() -> None:
    pass
