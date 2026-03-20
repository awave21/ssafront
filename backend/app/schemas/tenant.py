from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = Field(min_length=1, max_length=200)
    plan: str
    is_active: bool
    owner_user_id: UUID | None = None
    function_rules_enabled: bool = True
    function_rules_allow_semantic: bool = True
    created_at: datetime
    updated_at: datetime | None = None


class TenantBalanceRead(BaseModel):
    initial_balance_usd: Decimal
    spent_usd: Decimal
    remaining_usd: Decimal
    currency: str = "USD"
    updated_at: datetime | None = None


class TenantBalanceUpdate(BaseModel):
    initial_balance_usd: Decimal = Field(ge=0)
