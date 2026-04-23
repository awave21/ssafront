"""Общая библиотека KG-сущностей уровня агента (Motive / Argument / Proof / ...)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


ENTITY_TYPES = (
    "motive",
    "argument",
    "proof",
    "objection",
    "constraint",
    "outcome",
)


class AgentKgEntity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Переиспользуемая сущность графа знаний (в пределах одного агента).

    Узлы потоков (ScriptFlow) ссылаются на неё через
    `flow_definition.nodes[].data.kg_links.<type>_ids[]`.
    """

    __tablename__ = "agent_kg_entities"
    __table_args__ = (
        UniqueConstraint(
            "agent_id",
            "entity_type",
            "name_lc",
            name="uq_agent_kg_entity_agent_type_name",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # lower-cased name для уникальности без учёта регистра
    name_lc: Mapped[str] = mapped_column(
        String(200), nullable=False, server_default=""
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
