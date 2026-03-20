from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.credential import Credential
from app.services.credentials import decrypt_config
from app.services.sqns.client import SQNSClient


class SqnsClientConfigurationError(ValueError):
    """Ошибка конфигурации SQNS клиента."""


async def build_sqns_client_for_agent(
    db: AsyncSession,
    agent: Agent,
    *,
    tenant_id: UUID | None = None,
) -> SQNSClient:
    if not agent.sqns_enabled or not agent.sqns_host or not agent.sqns_credential_id:
        raise SqnsClientConfigurationError("SQNS integration is not configured")

    stmt = select(Credential).where(
        Credential.id == agent.sqns_credential_id,
        Credential.is_active.is_(True),
    )
    if tenant_id is not None:
        stmt = stmt.where(Credential.tenant_id == tenant_id)
    credential = (await db.execute(stmt)).scalar_one_or_none()
    if credential is None:
        raise SqnsClientConfigurationError("Active SQNS credential not found")

    try:
        config = decrypt_config(credential.config)
    except ValueError as exc:
        raise SqnsClientConfigurationError(str(exc)) from exc

    api_key = config.get("value") or config.get("api_key") or config.get("key") or config.get("token")
    if not api_key:
        raise SqnsClientConfigurationError("SQNS credential is missing an API key")

    token_path = config.get("token_path") or config.get("tokenEndpoint")
    bearer_token = str(api_key) if config.get("direct_bearer") else None
    return SQNSClient(
        agent.sqns_host,
        str(api_key),
        token_path=token_path,
        bearer_token=bearer_token,
    )
