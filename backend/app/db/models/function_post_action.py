from __future__ import annotations

from typing import Any, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.function_rule import FunctionRule


class FunctionPostAction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "function_post_actions"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    rule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("function_rules.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(
        Enum(
            "set_tag",
            "send_message",
            "webhook",
            "pause_dialog",
            "augment_prompt",
            "set_result",
            "noop",
            "block_user",
            "unblock_user",
            "resume_dialog",
            "send_delayed",
            name="function_post_action_type",
        ),
        nullable=False,
    )
    action_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    on_status: Mapped[str] = mapped_column(
        Enum("success", "error", "always", name="function_post_action_on_status"),
        default="always",
        server_default="always",
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    rule: Mapped["FunctionRule"] = relationship(back_populates="actions")
