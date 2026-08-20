"""Expert skills as a standalone entity + soft-delete on script_flows.

Разделяет навыки и потоки на уровне данных:
  - Новая таблица expert_skills — навык это самостоятельная сущность (skill_doc,
    service_external_ids, status, мягкое удаление). НЕ связан жёстко с потоком:
    дистилляция из потока — разовый импорт, ссылки не хранится.
  - script_flows получает is_deleted/deleted_at (SoftDeleteMixin) — удаление
    потока/навыка теперь мягкое и восстановимое (была безвозвратная потеря).
  - Данные: существующие script_flows.skill_doc (не пустые) переносятся в
    expert_skills. Колонка script_flows.skill_doc остаётся (не дропаем —
    неразрушающе), но UI/рантайм навыков больше её не используют.

Revision ID: 0101
Revises: 0100
Create Date: 2026-07-12
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0101"
down_revision: Union[str, None] = "0100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) soft-delete на script_flows
    op.add_column(
        "script_flows",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "script_flows",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 2) новая таблица навыков
    op.create_table(
        "expert_skills",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "agent_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("service_external_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("skill_doc", JSONB, nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "published", name="expert_skill_status"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_expert_skills_tenant_id", "expert_skills", ["tenant_id"])
    op.create_index("ix_expert_skills_agent_id", "expert_skills", ["agent_id"])

    # 3) перенос существующих навыков (script_flows.skill_doc → expert_skills)
    op.execute(
        """
        INSERT INTO expert_skills
            (id, tenant_id, agent_id, name, service_external_ids, skill_doc, status,
             is_deleted, created_at, updated_at)
        SELECT gen_random_uuid(), sf.tenant_id, sf.agent_id, sf.name,
               COALESCE(sf.service_external_ids, '[]'::jsonb),
               sf.skill_doc,
               CASE WHEN sf.flow_status = 'published' THEN 'published' ELSE 'draft' END,
               false, now(), now()
        FROM script_flows sf
        WHERE sf.skill_doc IS NOT NULL
          AND sf.skill_doc::text NOT IN ('null', '{}')
        """
    )


def downgrade() -> None:
    op.drop_index("ix_expert_skills_agent_id", table_name="expert_skills")
    op.drop_index("ix_expert_skills_tenant_id", table_name="expert_skills")
    op.drop_table("expert_skills")
    op.execute("DROP TYPE IF EXISTS expert_skill_status")
    op.drop_column("script_flows", "deleted_at")
    op.drop_column("script_flows", "is_deleted")
