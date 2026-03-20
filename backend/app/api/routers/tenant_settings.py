"""Tenant-level settings: manage per-org settings and OpenAI API keys."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role, require_scope
from app.db.models.tenant import Tenant
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.tenant import TenantBalanceRead, TenantBalanceUpdate, TenantRead
from app.schemas.tenant_llm_config import (
    TenantLLMConfigRead,
    TenantLLMConfigSet,
    TenantLLMConfigStatus,
)
from app.services.tenant_balance import get_tenant_balance, set_tenant_initial_balance
from app.services.tenant_llm_config import (
    delete_tenant_llm_key,
    get_tenant_llm_config,
    set_tenant_llm_key,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


class TenantNameUpdate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)


class TenantFunctionRulesUpdate(BaseModel):
    function_rules_enabled: bool | None = None
    function_rules_allow_semantic: bool | None = None


@router.patch("/name", response_model=TenantRead, status_code=status.HTTP_200_OK)
async def update_tenant_name(
    body: TenantNameUpdate,
    user: AuthContext = Depends(require_scope("settings:write")),
    db: AsyncSession = Depends(get_db),
):
    """Update the organization's display name."""
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    normalized_name = body.name.strip()
    if len(normalized_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Organization name must be at least 2 characters long",
        )

    tenant.name = normalized_name
    await db.commit()
    await db.refresh(tenant)
    logger.info(
        "tenant_name_updated",
        tenant_id=str(user.tenant_id),
        user_id=str(user.user_id),
    )
    return tenant


@router.patch("/function-rules", response_model=TenantRead, status_code=status.HTTP_200_OK)
async def update_tenant_function_rules(
    body: TenantFunctionRulesUpdate,
    user: AuthContext = Depends(require_scope("settings:write")),
    db: AsyncSession = Depends(get_db),
):
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if body.function_rules_enabled is not None:
        tenant.function_rules_enabled = body.function_rules_enabled
    if body.function_rules_allow_semantic is not None:
        tenant.function_rules_allow_semantic = body.function_rules_allow_semantic
    await db.commit()
    await db.refresh(tenant)
    logger.info("tenant_function_rules_flags_updated", tenant_id=str(user.tenant_id), user_id=str(user.user_id))
    return tenant


@router.get("/balance", response_model=TenantBalanceRead, status_code=status.HTTP_200_OK)
async def get_tenant_balance_settings(
    user: AuthContext = Depends(require_scope("settings:read")),
    db: AsyncSession = Depends(get_db),
):
    balance = await get_tenant_balance(db, tenant_id=user.tenant_id)
    if balance is None:
        return TenantBalanceRead(
            initial_balance_usd=0,
            spent_usd=0,
            remaining_usd=0,
            currency="USD",
            updated_at=None,
        )
    remaining_usd = balance.initial_balance_usd - balance.spent_usd
    return TenantBalanceRead(
        initial_balance_usd=balance.initial_balance_usd,
        spent_usd=balance.spent_usd,
        remaining_usd=remaining_usd,
        currency=balance.currency,
        updated_at=balance.updated_at,
    )


@router.patch("/balance", response_model=TenantBalanceRead, status_code=status.HTTP_200_OK)
async def update_tenant_balance_settings(
    body: TenantBalanceUpdate,
    _: AuthContext = Depends(require_scope("settings:write")),
    user: AuthContext = Depends(require_role("admin", "owner")),
    db: AsyncSession = Depends(get_db),
):
    balance = await set_tenant_initial_balance(
        db,
        tenant_id=user.tenant_id,
        initial_balance_usd=body.initial_balance_usd,
    )
    await db.commit()
    await db.refresh(balance)
    remaining_usd = balance.initial_balance_usd - balance.spent_usd
    return TenantBalanceRead(
        initial_balance_usd=balance.initial_balance_usd,
        spent_usd=balance.spent_usd,
        remaining_usd=remaining_usd,
        currency=balance.currency,
        updated_at=balance.updated_at,
    )


@router.get("/llm-key", response_model=TenantLLMConfigStatus)
async def get_llm_key_status(
    provider: str = "openai",
    user: AuthContext = Depends(require_scope("settings:read")),
    db: AsyncSession = Depends(get_db),
):
    """Check whether the organization has a custom OpenAI API key configured."""
    config = await get_tenant_llm_config(db, user.tenant_id, provider)
    if config is None or not config.is_active:
        return TenantLLMConfigStatus(has_key=False, provider=provider)
    return TenantLLMConfigStatus(
        has_key=True,
        provider=config.provider,
        last4=config.last4,
        is_active=config.is_active,
    )


@router.put("/llm-key", response_model=TenantLLMConfigRead, status_code=status.HTTP_200_OK)
async def set_llm_key(
    body: TenantLLMConfigSet,
    user: AuthContext = Depends(require_scope("settings:write")),
    db: AsyncSession = Depends(get_db),
):
    """Set or update the organization's OpenAI API key.

    The key is encrypted at rest via Fernet. Only the last 4 characters
    are stored in plaintext for identification purposes.
    """
    if body.provider == "openai" and not body.api_key.startswith("sk-"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="OpenAI API keys must start with 'sk-'",
        )

    row = await set_tenant_llm_key(db, user.tenant_id, body.api_key, body.provider)
    await db.commit()
    await db.refresh(row)
    logger.info(
        "tenant_llm_key_set",
        tenant_id=str(user.tenant_id),
        provider=body.provider,
        user_id=str(user.user_id),
    )
    return row


@router.delete("/llm-key", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_key(
    provider: str = "openai",
    user: AuthContext = Depends(require_scope("settings:write")),
    db: AsyncSession = Depends(get_db),
):
    """Remove (deactivate) the organization's custom OpenAI API key.

    After deletion, OpenAI requests are blocked until a new key is configured.
    """
    deleted = await delete_tenant_llm_key(db, user.tenant_id, provider)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No LLM key configured for this provider",
        )
    await db.commit()
    logger.info(
        "tenant_llm_key_deleted",
        tenant_id=str(user.tenant_id),
        provider=provider,
        user_id=str(user.user_id),
    )
