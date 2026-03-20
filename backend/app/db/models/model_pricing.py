from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ModelPricing(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "model_pricing"
    __table_args__ = (
        UniqueConstraint("provider", "model_name", name="uq_model_pricing_provider_model_name"),
    )

    provider: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    model_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Цены хранятся за 1_000_000 токенов.
    input_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    output_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cached_input_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    reasoning_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))

    input_rub: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    output_rub: Mapped[Decimal] = mapped_column(Numeric(18, 8), nullable=False)
    cached_input_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    reasoning_rub: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
