from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class TenantBalance(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenant_balances"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_tenant_balances_tenant_id"),)

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD", nullable=False)
    initial_balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 10),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    spent_usd: Mapped[Decimal] = mapped_column(
        Numeric(18, 10),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
