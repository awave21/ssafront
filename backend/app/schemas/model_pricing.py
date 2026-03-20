from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelPricingBase(BaseModel):
    provider: str = Field(min_length=1, max_length=100, description="Провайдер модели (например, openai)")
    model_name: str = Field(min_length=1, max_length=200, description="Имя модели")
    display_name: str | None = Field(default=None, max_length=300, description="Человекочитаемое имя модели")
    is_active: bool = Field(default=True, description="Активна ли запись тарифа")

    # Все цены задаются за 1_000_000 токенов.
    input_usd: Decimal = Field(..., ge=0, description="Цена input токенов в USD за 1M")
    output_usd: Decimal = Field(..., ge=0, description="Цена output токенов в USD за 1M")
    cached_input_usd: Decimal | None = Field(None, ge=0, description="Цена cached input в USD за 1M")
    reasoning_usd: Decimal | None = Field(None, ge=0, description="Цена reasoning токенов в USD за 1M")

    input_rub: Decimal = Field(..., ge=0, description="Цена input токенов в RUB за 1M")
    output_rub: Decimal = Field(..., ge=0, description="Цена output токенов в RUB за 1M")
    cached_input_rub: Decimal | None = Field(None, ge=0, description="Цена cached input в RUB за 1M")
    reasoning_rub: Decimal | None = Field(None, ge=0, description="Цена reasoning токенов в RUB за 1M")


class ModelPricingCreate(ModelPricingBase):
    pass


class ModelPricingUpdate(BaseModel):
    provider: str | None = Field(default=None, min_length=1, max_length=100)
    model_name: str | None = Field(default=None, min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=300)
    is_active: bool | None = None

    input_usd: Decimal | None = Field(None, ge=0)
    output_usd: Decimal | None = Field(None, ge=0)
    cached_input_usd: Decimal | None = Field(None, ge=0)
    reasoning_usd: Decimal | None = Field(None, ge=0)

    input_rub: Decimal | None = Field(None, ge=0)
    output_rub: Decimal | None = Field(None, ge=0)
    cached_input_rub: Decimal | None = Field(None, ge=0)
    reasoning_rub: Decimal | None = Field(None, ge=0)


class ModelPricingRead(ModelPricingBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class ActiveModelOption(BaseModel):
    value: str = Field(..., description="Значение для селекта в формате provider:model_name")
    provider: str = Field(..., description="Провайдер модели")
    model_name: str = Field(..., description="Системное имя модели")
    label: str = Field(..., description="Отображаемое имя в UI")


class ActiveModelGroup(BaseModel):
    group: str = Field(..., description="Название группы моделей (optgroup)")
    options: list[ActiveModelOption] = Field(default_factory=list)
