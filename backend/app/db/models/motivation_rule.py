from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

MotivationRole = Literal["doctor"]


class MotivationRule(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "motivation_rules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "role", name="uq_motivation_rule_tenant_role"),
    )

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="doctor")

    # % от выручки первичных визитов
    primary_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("15.00"))

    # % со вторичных визитов: три уровня
    repeat_pct_low: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("17.00"))
    repeat_pct_norm: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("20.00"))
    repeat_pct_high: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("22.00"))

    # Диапазон нормы среднего чека первичных визитов
    avg_check_low: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("44000.00"))
    avg_check_high: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("60000.00"))

    # Учитывать ли выручку от товаров при расчёте бонуса
    include_commodities: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
