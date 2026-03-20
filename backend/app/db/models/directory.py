from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class Directory(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Справочник — структурированный набор данных, который становится tool'ом агента."""

    __tablename__ = "directories"
    __table_args__ = (
        UniqueConstraint("agent_id", "slug", name="uq_directories_agent_slug"),
        UniqueConstraint("agent_id", "tool_name", name="uq_directories_agent_tool_name"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Основные поля
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Шаблон и структура
    template: Mapped[str] = mapped_column(
        Enum(
            "qa",
            "service_catalog",
            "product_catalog",
            "company_info",
            "custom",
            name="directory_template",
        ),
        default="custom",
        nullable=False,
    )
    columns: Mapped[list[dict]] = mapped_column(JSONB, default=list, nullable=False)

    # Настройки поведения
    response_mode: Mapped[str] = mapped_column(
        Enum("function_result", "direct_message", name="directory_response_mode"),
        default="function_result",
        nullable=False,
    )
    search_type: Mapped[str] = mapped_column(
        Enum("exact", "fuzzy", "semantic", name="directory_search_type"),
        default="fuzzy",
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Метаданные
    items_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    agent: Mapped["Agent"] = relationship("Agent", back_populates="directories")
    items: Mapped[list["DirectoryItem"]] = relationship(
        "DirectoryItem",
        back_populates="directory",
        cascade="all, delete-orphan",
    )


class DirectoryItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Запись справочника."""

    __tablename__ = "directory_items"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    directory_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("directories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    # Embedding для семантического поиска через pgvector (1536 = OpenAI text-embedding-3-small)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)

    # Relationships
    directory: Mapped["Directory"] = relationship("Directory", back_populates="items")
