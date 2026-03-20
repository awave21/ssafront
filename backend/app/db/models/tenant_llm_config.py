from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TenantLLMConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenant_llm_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_llm_config_provider"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="openai")
    encrypted_api_key: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    last4: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
