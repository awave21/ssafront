from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class ExpertSkill(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Навык эксперта — самостоятельная сущность («продолжение эксперта»).

    Отделён от script_flows: навык это дистиллированный/написанный опыт по услуге
    (skill_doc), который правится в чате/структуре и публикуется для рантайма
    (навык-слой + тул use_expert_skill). НЕ связан жёстко с граф-потоком: может
    быть создан из потока разовым импортом или написан с нуля. Удаление — мягкое
    (SoftDeleteMixin), поток-источник (если был) не затрагивается и наоборот.
    """

    __tablename__ = "expert_skills"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Явная связь навык↔услуги (внешние id услуг SQNS) — по ней навык-слой рантайма
    # подбирает навык для активной услуги диалога.
    service_external_ids: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    # Структура навыка: context/objections[phrases]/sequence/facts_from_tool/endings/gaps.
    skill_doc: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("draft", "published", name="expert_skill_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )

    agent: Mapped["Agent"] = relationship("Agent")
