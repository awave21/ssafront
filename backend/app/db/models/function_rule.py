from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent
    from app.db.models.tool import Tool
    from app.db.models.function_post_action import FunctionPostAction


class FunctionRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "function_rules"
    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_function_rule_agent_name"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tool_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    stop_on_match: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    allow_semantic: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    trigger_mode: Mapped[str] = mapped_column(
        Enum("pre_run", "post_tool", "post_run", name="function_rule_trigger_mode"),
        default="pre_run",
        server_default="pre_run",
        nullable=False,
    )
    condition_type: Mapped[str] = mapped_column(
        Enum("keyword", "regex", "semantic", "json_context", "always", name="function_rule_condition_type"),
        default="keyword",
        server_default="keyword",
        nullable=False,
    )
    condition_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    reaction_to_execution: Mapped[str] = mapped_column(
        Enum(
            "send_message",
            "ai_instruction",
            "ai_self_reply",
            "silent",
            name="function_rule_reaction_to_execution",
        ),
        default="ai_self_reply",
        server_default="ai_self_reply",
        nullable=False,
    )
    behavior_after_execution: Mapped[str] = mapped_column(
        Enum(
            "continue",
            "pause",
            "augment_prompt",
            name="function_rule_behavior_after_execution",
        ),
        default="continue",
        server_default="continue",
        nullable=False,
    )

    agent: Mapped["Agent"] = relationship(back_populates="function_rules")
    tool: Mapped["Tool | None"] = relationship()
    actions: Mapped[list["FunctionPostAction"]] = relationship(
        back_populates="rule",
        cascade="all, delete-orphan",
    )
