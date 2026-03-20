from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class Channel(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "channels"
    __table_args__ = (
        UniqueConstraint("telegram_webhook_token", name="uq_channels_telegram_webhook_token"),
    )

    type: Mapped[str] = mapped_column(
        Enum("telegram", "telegram_phone", "whatsapp", "max", name="channel_type"),
        nullable=False,
        index=True,
    )
    wappi_profile_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    phone_is_authorized: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    telegram_bot_token: Mapped[str | None] = mapped_column(String(200), nullable=True)
    telegram_webhook_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    telegram_webhook_token: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telegram_webhook_secret: Mapped[str | None] = mapped_column(String(120), nullable=True)
    telegram_webhook_endpoint: Mapped[str | None] = mapped_column(String(500), nullable=True)

    agent_links: Mapped[list["AgentChannel"]] = relationship(
        "AgentChannel",
        back_populates="channel",
        cascade="all, delete-orphan",
    )


class AgentChannel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_channels"
    __table_args__ = (
        UniqueConstraint("agent_id", "channel_id", name="uq_agent_channels_agent_channel"),
    )

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    agent: Mapped["Agent"] = relationship(
        "Agent",
        back_populates="channel_links",
    )
    channel: Mapped["Channel"] = relationship(
        "Channel",
        back_populates="agent_links",
    )
