"""Service layer for per-tenant LLM API key management.

Encrypts keys with the same Fernet mechanism used for Credential configs.
"""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tenant_llm_config import TenantLLMConfig
from app.services.credentials import decrypt_config, encrypt_config

logger = structlog.get_logger(__name__)

_KEY_FIELD = "api_key"


async def get_tenant_llm_config(
    db: AsyncSession,
    tenant_id: UUID,
    provider: str = "openai",
) -> TenantLLMConfig | None:
    stmt = select(TenantLLMConfig).where(
        TenantLLMConfig.tenant_id == tenant_id,
        TenantLLMConfig.provider == provider,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_decrypted_api_key(
    db: AsyncSession,
    tenant_id: UUID,
    provider: str = "openai",
) -> str | None:
    """Return decrypted API key for the tenant, or None when not configured.

    Safe to call before the migration is applied — returns None on DB errors.
    """
    try:
        config = await get_tenant_llm_config(db, tenant_id, provider)
    except Exception:
        logger.debug("tenant_llm_config_table_not_ready", tenant_id=str(tenant_id))
        return None
    if config is None or not config.is_active:
        return None
    try:
        decrypted = decrypt_config(config.encrypted_api_key)
        return decrypted.get(_KEY_FIELD)
    except Exception:
        logger.exception("tenant_llm_key_decrypt_failed", tenant_id=str(tenant_id), provider=provider)
        return None


async def set_tenant_llm_key(
    db: AsyncSession,
    tenant_id: UUID,
    api_key: str,
    provider: str = "openai",
) -> TenantLLMConfig:
    """Create or update the API key for the tenant+provider pair."""
    existing = await get_tenant_llm_config(db, tenant_id, provider)
    encrypted = encrypt_config({_KEY_FIELD: api_key})
    last4 = api_key[-4:]

    if existing:
        existing.encrypted_api_key = encrypted
        existing.last4 = last4
        existing.is_active = True
        await db.flush()
        logger.info("tenant_llm_key_updated", tenant_id=str(tenant_id), provider=provider)
        return existing

    row = TenantLLMConfig(
        tenant_id=tenant_id,
        provider=provider,
        encrypted_api_key=encrypted,
        last4=last4,
        is_active=True,
    )
    db.add(row)
    await db.flush()
    logger.info("tenant_llm_key_created", tenant_id=str(tenant_id), provider=provider)
    return row


async def delete_tenant_llm_key(
    db: AsyncSession,
    tenant_id: UUID,
    provider: str = "openai",
) -> bool:
    """Deactivate (soft-delete) the key. Returns True if a key existed."""
    config = await get_tenant_llm_config(db, tenant_id, provider)
    if config is None:
        return False
    config.is_active = False
    await db.flush()
    logger.info("tenant_llm_key_deactivated", tenant_id=str(tenant_id), provider=provider)
    return True
