from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.credential import Credential
    from app.db.models.channel import AgentChannel
    from app.db.models.directory import Directory
    from app.db.models.direct_question import DirectQuestion
    from app.db.models.function_rule import FunctionRule
    from app.db.models.knowledge_file import KnowledgeFile
    from app.db.models.script_flow import ScriptFlow


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "agents"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    llm_params: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("draft", "published", name="agent_status"),
        default="draft",
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sqns_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    sqns_configured: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    sqns_host: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sqns_credential_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("credentials.id"),
        nullable=True,
    )
    sqns_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sqns_last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sqns_last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sqns_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sqns_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    sqns_disabled_tools: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        server_default="[]",
        nullable=False,
    )
    sqns_tool_descriptions: Mapped[dict[str, str]] = mapped_column(
        JSONB,
        default=dict,
        server_default="{}",
        nullable=False,
    )
    max_history_messages: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_tool_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    direct_questions_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    knowledge_tool_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    manager_pause_minutes: Mapped[int] = mapped_column(Integer, default=10, server_default="10", nullable=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", server_default="UTC", nullable=False)
    function_rules_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    function_rules_allow_semantic: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False,
    )
    # Режим инжекции в системный промпт (всё, чего нет в UI-редакторе, — «скрыто»):
    #   "manual" — (умолчание) никаких скрытых вставок: только agent.system_prompt
    #              + сценарии/вебхуки, если сами явно его меняют. Без bridge,
    #              без снимка state, без стиля эксперта, без даты/времени, без
    #              автодобавок SQNS. Состояние и стиль остаются в ответах тулов.
    #   "auto"   — обратная совместимость: bridge, state, стиль, дата/время, SQNS-block.
    runtime_bridges_mode: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )

    bindings: Mapped[list["AgentToolBinding"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )

    runs: Mapped[list["Run"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    channel_links: Mapped[list["AgentChannel"]] = relationship(
        "AgentChannel",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    sqns_credential: Mapped[Optional["Credential"]] = relationship(
        "Credential",
        primaryjoin="Agent.sqns_credential_id==Credential.id",
        viewonly=True,
        lazy="select",
        uselist=False,
    )
    directories: Mapped[list["Directory"]] = relationship(
        "Directory",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    direct_questions: Mapped[list["DirectQuestion"]] = relationship(
        "DirectQuestion",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    function_rules: Mapped[list["FunctionRule"]] = relationship(
        "FunctionRule",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    knowledge_files: Mapped[list["KnowledgeFile"]] = relationship(
        "KnowledgeFile",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    script_flows: Mapped[list["ScriptFlow"]] = relationship(
        "ScriptFlow",
        back_populates="agent",
        cascade="all, delete-orphan",
    )
