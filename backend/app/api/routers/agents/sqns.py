from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Awaitable, Callable, TypeVar
from uuid import UUID

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl, model_validator
from sqlalchemy import desc, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_scope, require_scope_any
from app.db.models.agent import Agent
from app.db.models.credential import Credential
from app.db.models.sqns_service import SqnsClientRecord, SqnsPayment
from app.db.session import get_db
from app.schemas.agent import AgentRead, SqnsStatus, SqnsTool, get_sqns_tools_definitions
from app.schemas.auth import AuthContext
from app.schemas.sqns_service import (
    SqnsCategoryRead,
    SqnsCategoryUpdate,
    SqnsClientCachedVisitItem,
    SqnsClientCachedVisitsResponse,
    SqnsClientListItem,
    SqnsClientsListResponse,
    SqnsSpecialistListItem,
    SqnsSpecialistUpdate,
    SqnsServiceBulkUpdate,
    SqnsServiceRead,
    SqnsServiceUpdate,
)
from app.services.audit import write_audit
from app.services.credentials import encrypt_config
from app.services.sqns import SQNSClient, SQNSClientError, fetch_token_by_login
from app.services.sqns.client_factory import SqnsClientConfigurationError, build_sqns_client_for_agent
from app.services.sqns.sync import sync_sqns_entities
from app.services.sqns.sync_locks import sqns_agent_lock
from app.schemas.analytics import AnalyticsRevenueBasis
from app.services.analytics import (
    build_analytics_period,
    _dedupe_payments_for_revenue,
    _extract_client_tags,
    _extract_visit_channel,
    _normalize_channel,
    _normalize_text,
    _payment_allowed_for_revenue_basis,
    resolve_revenue_category_handles,
)
from app.services.sqns.sync_handlers.visits import sqns_visit_datetime_raw_string
from app.services.sqns.visit_arrival import is_sqns_visit_arrived

from app.api.routers.agents.deps import get_agent_or_404

logger = structlog.get_logger()

router = APIRouter()

T = TypeVar("T")


def _extract_price_range(raw_data: dict[str, Any] | None) -> str | None:
    if not isinstance(raw_data, dict):
        return None
    cand = raw_data.get("price") or raw_data.get("priceRange")
    if isinstance(cand, dict):
        rng = cand.get("range")
        if isinstance(rng, list) and len(rng) >= 2:
            first = rng[0]
            last = rng[-1]
            return f"{first} — {last}"
        minimum = cand.get("min") or cand.get("minimum")
        maximum = cand.get("max") or cand.get("maximum")
        if minimum is not None and maximum is not None:
            return f"{minimum} — {maximum}"
        values = [
            cand.get("from"),
            cand.get("to"),
            cand.get("value"),
            cand.get("amount"),
        ]
        filtered = [str(v) for v in values if v is not None]
        if filtered:
            return " / ".join(filtered)
    if isinstance(cand, list) and len(cand) >= 2:
        return f"{cand[0]} — {cand[-1]}"
    return None


def _extract_raw_text(raw_data: dict[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if not isinstance(raw_data, dict):
        return None
    for key in keys:
        value = raw_data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _extract_employee_service_ids(raw_data: dict[str, Any] | None) -> list[int]:
    if not isinstance(raw_data, dict):
        return []
    keys = (
        "services",
        "serviceIds",
        "service_ids",
        "linkedServices",
        "allowedServices",
        "employeeServices",
        "serviceList",
        "servicesList",
    )
    out: list[int] = []
    seen: set[int] = set()
    for key in keys:
        payload = raw_data.get(key)
        if payload is None:
            continue
        seq: list[Any] | None = None
        if isinstance(payload, list):
            seq = payload
        elif isinstance(payload, dict):
            for nested in ("services", "items", "data"):
                value = payload.get(nested)
                if isinstance(value, list):
                    seq = value
                    break
        if not isinstance(seq, list):
            continue
        for item in seq:
            value: Any = item
            if isinstance(item, dict):
                value = item.get("id") or item.get("serviceId") or item.get("service_id")
            try:
                sid = int(value)
            except (TypeError, ValueError):
                continue
            if sid in seen:
                continue
            seen.add(sid)
            out.append(sid)
    return out


def _normalize_sqns_host(host: str) -> str:
    host = (host or "").strip().rstrip("/")
    if not host:
        raise ValueError("host is required")
    if host.startswith(("http://", "https://")):
        return host
    return f"https://{host}"


async def _build_sqns_client(agent: Agent, db: AsyncSession, user: AuthContext) -> SQNSClient:
    try:
        return await build_sqns_client_for_agent(db, agent, tenant_id=user.tenant_id)
    except SqnsClientConfigurationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _update_sqns_status(
    db: AsyncSession,
    agent: Agent,
    *,
    status_text: str = "ok",
    error: str | None = None,
) -> None:
    agent.sqns_status = status_text
    agent.sqns_error = error
    agent.sqns_last_activity_at = datetime.utcnow()
    await db.commit()
    await db.refresh(agent)


async def _execute_sqns_action(
    agent: Agent,
    db: AsyncSession,
    client: SQNSClient,
    action: Callable[[SQNSClient], Awaitable[T]],
) -> T:
    try:
        result = await action(client)
    except SQNSClientError as exc:
        await _update_sqns_status(db, agent, status_text="error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    await _update_sqns_status(db, agent)
    return result


class AgentSQNSEnable(BaseModel):
    host: HttpUrl
    api_key: str = Field(min_length=1)
    token_path: str | None = None
    direct_bearer: bool = False


class AgentSQNSEnableByPassword(BaseModel):
    """Фронт: host, email, password; бэкенд получает токен через login и сохраняет его."""

    host: str = Field(min_length=1, description="Хост SQNS, например crmexchange.1denta.ru")
    email: str = Field(min_length=1)
    password: str = Field(min_length=1)
    default_resource_id: int | None = Field(
        default=None,
        alias="defaultResourceId",
        description="Опционально",
    )


class SqnsToolToggleRequest(BaseModel):
    enabled: bool | None = Field(default=None, description="Включить или выключить SQNS-инструмент для агента")
    description: str | None = Field(default=None, description="Кастомное описание SQNS-инструмента")

    @model_validator(mode="after")
    def _validate_non_empty_update(self) -> "SqnsToolToggleRequest":
        if self.enabled is None and self.description is None:
            raise ValueError("Provide at least one field: enabled or description")
        return self


def _list_sqns_tool_names() -> set[str]:
    return {str(item["name"]) for item in get_sqns_tools_definitions() if isinstance(item, dict) and item.get("name")}


def _normalize_sqns_disabled_tools(agent: Agent) -> list[str]:
    raw = agent.sqns_disabled_tools if isinstance(agent.sqns_disabled_tools, list) else []
    valid_names = _list_sqns_tool_names()
    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw:
        name = str(item).strip()
        if not name or name not in valid_names or name in seen:
            continue
        seen.add(name)
        normalized.append(name)
    return normalized


def _normalize_sqns_tool_descriptions(agent: Agent) -> dict[str, str]:
    raw = agent.sqns_tool_descriptions if isinstance(agent.sqns_tool_descriptions, dict) else {}
    valid_names = _list_sqns_tool_names()
    normalized: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key).strip()
        description = str(value).strip()
        if not name or name not in valid_names:
            continue
        if not description:
            continue
        normalized[name] = description
    return normalized


@router.post("/{agent_id}/sqns/enable", response_model=AgentRead)
async def enable_sqns_integration(
    agent_id: UUID,
    payload: AgentSQNSEnable,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentRead:
    agent = await get_agent_or_404(agent_id, db, user)
    client = SQNSClient(
        str(payload.host),
        payload.api_key,
        token_path=payload.token_path,
        bearer_token=payload.api_key if payload.direct_bearer else None,
    )
    try:
        await client.list_resources()
    except SQNSClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    credential_name = f"sqns-{agent.id}"
    stmt = (
        select(Credential)
        .where(Credential.tenant_id == user.tenant_id, Credential.name == credential_name)
    )
    credential = (await db.execute(stmt)).scalar_one_or_none()
    config_payload: dict[str, Any] = {"value": payload.api_key}
    if payload.token_path:
        config_payload["token_path"] = payload.token_path
    if payload.direct_bearer:
        config_payload["direct_bearer"] = True
    encrypted_config = encrypt_config(config_payload)

    if credential:
        credential.config = encrypted_config
        credential.auth_type = "api_key"
        credential.is_active = True
    else:
        credential = Credential(
            tenant_id=user.tenant_id,
            name=credential_name,
            auth_type="api_key",
            config=encrypted_config,
            is_active=True,
        )
        db.add(credential)
        await db.flush()

    agent.sqns_enabled = True
    agent.sqns_configured = True
    agent.sqns_host = str(payload.host)
    agent.sqns_credential_id = credential.id
    agent.sqns_status = "ok"
    agent.sqns_error = None
    agent.sqns_last_activity_at = datetime.utcnow()
    await db.commit()
    await db.refresh(agent)
    await write_audit(db, user, "agent.sqns.enable", "agent", str(agent.id))
    return AgentRead.model_validate(agent)


@router.get("/{agent_id}/sqns", response_model=SqnsStatus)
async def get_sqns_status(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> SqnsStatus:
    """Получить статус интеграции SQNS для агента."""
    agent = await get_agent_or_404(agent_id, db, user)

    tools = []
    if agent.sqns_enabled:
        disabled_tools = set(_normalize_sqns_disabled_tools(agent))
        description_overrides = _normalize_sqns_tool_descriptions(agent)
        for defn in get_sqns_tools_definitions():
            tool_name = str(defn["name"])
            tools.append(
                SqnsTool(
                    name=tool_name,
                    description=description_overrides.get(tool_name, defn["description"]),
                    isEnabled=tool_name not in disabled_tools,
                    requiredFields=defn["schema"].get("required", []),
                    dataSources={},  # Можно будет наполнить позже
                )
            )

    return SqnsStatus(
        sqnsEnabled=agent.sqns_enabled,
        sqnsHost=agent.sqns_host,
        sqnsLastSyncAt=agent.sqns_last_sync_at,
        sqnsLastActivityAt=agent.sqns_last_activity_at,
        sqnsStatus=agent.sqns_status,
        sqnsError=agent.sqns_error,
        sqnsTools=tools,
    )


@router.patch("/{agent_id}/sqns/tools/{tool_name}", response_model=SqnsStatus)
async def toggle_sqns_tool(
    agent_id: UUID,
    tool_name: str,
    payload: SqnsToolToggleRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> SqnsStatus:
    """Обновить настройки конкретного SQNS-инструмента (enabled/description)."""
    agent = await get_agent_or_404(agent_id, db, user)
    valid_names = _list_sqns_tool_names()
    normalized_tool_name = tool_name.strip()
    if normalized_tool_name not in valid_names:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown SQNS tool: {normalized_tool_name}",
        )

    disabled = set(_normalize_sqns_disabled_tools(agent))
    if payload.enabled is not None:
        if payload.enabled:
            disabled.discard(normalized_tool_name)
        else:
            disabled.add(normalized_tool_name)
    agent.sqns_disabled_tools = sorted(disabled)

    descriptions = _normalize_sqns_tool_descriptions(agent)
    if payload.description is not None:
        normalized_description = payload.description.strip()
        if normalized_description:
            descriptions[normalized_tool_name] = normalized_description
        else:
            descriptions.pop(normalized_tool_name, None)
    agent.sqns_tool_descriptions = descriptions

    await db.commit()
    await db.refresh(agent)
    await write_audit(
        db,
        user,
        "agent.sqns.tool.toggle",
        "agent",
        str(agent.id),
        metadata={
            "tool_name": normalized_tool_name,
            "enabled": payload.enabled,
            "description_updated": payload.description is not None,
        },
    )
    return await get_sqns_status(agent_id=agent_id, db=db, user=user)


@router.post("/{agent_id}/sqns/enable-by-password", response_model=AgentRead)
async def enable_sqns_by_password(
    agent_id: UUID,
    payload: AgentSQNSEnableByPassword,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentRead:
    """
    Включить SQNS по email и паролю. Бэкенд запрашивает токен
    (POST {host}/api/v2/auth с JSON {email, password, defaultResourceId?}).
    Ответ: [{ "status": "success", "token": "...", "user": {...} }]. Токен сохраняется (direct_bearer).
    """
    agent = await get_agent_or_404(agent_id, db, user)
    try:
        base_url = _normalize_sqns_host(payload.host)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

    try:
        token = await fetch_token_by_login(
            base_url,
            payload.email,
            payload.password,
            default_resource_id=payload.default_resource_id,
        )
    except SQNSClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    client = SQNSClient(base_url, "", bearer_token=token)
    try:
        await client.list_resources()
    except SQNSClientError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    credential_name = f"sqns-{agent.id}"
    stmt = select(Credential).where(
        Credential.tenant_id == user.tenant_id,
        Credential.name == credential_name,
    )
    credential = (await db.execute(stmt)).scalar_one_or_none()
    config_payload: dict[str, Any] = {"value": token, "direct_bearer": True}
    if payload.default_resource_id is not None:
        config_payload["default_resource_id"] = payload.default_resource_id
    encrypted_config = encrypt_config(config_payload)

    if credential:
        credential.config = encrypted_config
        credential.auth_type = "api_key"
        credential.is_active = True
    else:
        credential = Credential(
            tenant_id=user.tenant_id,
            name=credential_name,
            auth_type="api_key",
            config=encrypted_config,
            is_active=True,
        )
        db.add(credential)
        await db.flush()

    # Проверка на дублирующиеся подключения (мягкое предупреждение)
    stmt = select(Agent).where(
        Agent.sqns_host == base_url,
        Agent.sqns_enabled == True,
        Agent.id != agent.id,
    )
    duplicate_agents = (await db.execute(stmt)).scalars().all()
    if duplicate_agents:
        agent.sqns_warning = (
            f"Внимание: {len(duplicate_agents)} других агентов уже подключены к этому SQNS аккаунту. "
            f"Это может привести к конфликтам данных."
        )
    else:
        agent.sqns_warning = None

    agent.sqns_enabled = True
    agent.sqns_configured = True
    agent.sqns_host = base_url
    agent.sqns_credential_id = credential.id
    agent.sqns_status = "ok"
    agent.sqns_error = None
    agent.sqns_last_activity_at = datetime.utcnow()
    await db.commit()
    await db.refresh(agent)

    # Автосинхронизация услуг после включения
    try:
        async with sqns_agent_lock(agent.id) as acquired:
            if acquired:
                sync_result = await sync_sqns_entities(
                    db=db,
                    sqns_client=client,
                    agent_id=agent.id,
                    trigger="enable_auto",
                )
                if sync_result.success:
                    agent.sqns_last_sync_at = sync_result.synced_at
                    agent.sqns_status = "ok"
                    agent.sqns_error = None
                    await db.commit()
                    await db.refresh(agent)
            else:
                logger.info("sqns_auto_sync_skipped_lock", agent_id=str(agent.id))
    except Exception as exc:
        logger.warning("sqns_auto_sync_failed", agent_id=str(agent.id), error=str(exc))
        # Не падаем, если синхронизация завершилась с ошибкой

    # После rollback внутри sync_service ORM-объект agent может стать "expired".
    # Перечитываем его явно, чтобы избежать MissingGreenlet на сериализации/аудите.
    agent = await get_agent_or_404(agent_id, db, user)
    await write_audit(db, user, "agent.sqns.enable_by_password", "agent", str(agent_id))
    return AgentRead.model_validate(agent)


@router.post("/{agent_id}/sqns/disable", response_model=AgentRead)
@router.delete("/{agent_id}/sqns", response_model=AgentRead)
async def disable_sqns_integration(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentRead:
    """
    Отключить SQNS интеграцию и выполнить HARD DELETE всех кэшированных данных.

    Удаляются:
    - sqns_resources (специалисты)
    - sqns_services (услуги)
    - sqns_commodities (товары)
    - sqns_employees (сотрудники)
    - sqns_clients (клиенты)
    - sqns_visit_commodity_lines (связи визит–товар из сырого API)
    - sqns_visits (визиты)
    - sqns_payments (платежи)
    - sqns_service_resources (связи)
    - sqns_service_categories (категории)
    - sqns_sync_cursor (курсоры синхронизации)
    - sqns_sync_runs (логи синхронизации)

    Удаление происходит автоматически через ON DELETE CASCADE.
    """
    from sqlalchemy import delete
    from app.db.models.sqns_service import (
        SqnsClientRecord,
        SqnsCommodity,
        SqnsEmployee,
        SqnsPayment,
        SqnsResource,
        SqnsService,
        SqnsServiceCategory,
        SqnsSyncCursor,
        SqnsSyncRun,
        SqnsVisit,
        SqnsVisitCommodityLine,
    )

    agent = await get_agent_or_404(agent_id, db, user)

    # Жесткое удаление всех кэшированных данных SQNS
    # SqnsServiceResource удалятся автоматически через CASCADE
    try:
        # Удаляем категории
        await db.execute(
            delete(SqnsServiceCategory).where(
                SqnsServiceCategory.agent_id == agent.id
            )
        )

        await db.execute(
            delete(SqnsSyncCursor).where(
                SqnsSyncCursor.agent_id == agent.id
            )
        )
        await db.execute(
            delete(SqnsSyncRun).where(
                SqnsSyncRun.agent_id == agent.id
            )
        )

        await db.execute(
            delete(SqnsPayment).where(
                SqnsPayment.agent_id == agent.id
            )
        )
        await db.execute(
            delete(SqnsVisitCommodityLine).where(
                SqnsVisitCommodityLine.agent_id == agent.id
            )
        )
        await db.execute(
            delete(SqnsVisit).where(
                SqnsVisit.agent_id == agent.id
            )
        )
        await db.execute(
            delete(SqnsCommodity).where(
                SqnsCommodity.agent_id == agent.id
            )
        )
        await db.execute(
            delete(SqnsEmployee).where(
                SqnsEmployee.agent_id == agent.id
            )
        )
        await db.execute(
            delete(SqnsClientRecord).where(
                SqnsClientRecord.agent_id == agent.id
            )
        )

        # Удаляем услуги (CASCADE удалит SqnsServiceResource)
        await db.execute(
            delete(SqnsService).where(
                SqnsService.agent_id == agent.id
            )
        )

        # Удаляем специалистов
        await db.execute(
            delete(SqnsResource).where(
                SqnsResource.agent_id == agent.id
            )
        )

        logger.info("sqns_cache_deleted", agent_id=str(agent.id))
    except Exception as exc:
        logger.error("sqns_cache_delete_failed", agent_id=str(agent.id), error=str(exc))
        # Продолжаем отключение, даже если удаление не удалось

    agent.sqns_enabled = False
    agent.sqns_configured = False
    agent.sqns_status = "disabled"
    agent.sqns_error = None
    agent.sqns_warning = None
    agent.sqns_last_sync_at = None
    agent.sqns_last_activity_at = None
    if agent.sqns_credential_id:
        stmt = select(Credential).where(
            Credential.id == agent.sqns_credential_id,
            Credential.tenant_id == user.tenant_id,
        )
        credential = (await db.execute(stmt)).scalar_one_or_none()
        if credential:
            credential.is_active = False
    await db.commit()
    await db.refresh(agent)
    await write_audit(db, user, "agent.sqns.disable", "agent", str(agent.id))
    return AgentRead.model_validate(agent)


@router.get("/{agent_id}/sqns/resources")
async def sqns_resources(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, Any]:
    agent = await get_agent_or_404(agent_id, db, user)
    client = await _build_sqns_client(agent, db, user)
    resources = await _execute_sqns_action(agent, db, client, lambda client: client.list_resources())
    return {"resources": resources}


@router.get("/{agent_id}/sqns/services")
async def sqns_services(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, Any]:
    agent = await get_agent_or_404(agent_id, db, user)
    client = await _build_sqns_client(agent, db, user)
    services = await _execute_sqns_action(agent, db, client, lambda client: client.list_services())
    return {"services": services}


@router.get("/{agent_id}/sqns/specialists")
async def sqns_list_cached_specialists(
    agent_id: UUID,
    search: str | None = None,
    is_active: bool | None = None,
    active: bool | None = None,
    limit: int = Query(200, ge=1, le=1000, description="Максимум результатов (1-1000)"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope_any("agents:write", "analytics:view")),
) -> dict[str, Any]:
    from sqlalchemy import func, select
    from app.db.models.sqns_service import SqnsResource, SqnsServiceResource

    agent = await get_agent_or_404(agent_id, db, user)

    count_stmt = select(func.count(SqnsResource.id)).where(SqnsResource.agent_id == agent.id)
    stmt = (
        select(
            SqnsResource,
            func.count(SqnsServiceResource.id).label("services_count"),
        )
        .outerjoin(
            SqnsServiceResource,
            SqnsServiceResource.resource_id == SqnsResource.id,
        )
        .where(SqnsResource.agent_id == agent.id)
        .group_by(SqnsResource.id)
    )

    if search:
        search_filter = (
            SqnsResource.name.ilike(f"%{search}%")
            | SqnsResource.specialization.ilike(f"%{search}%")
        )
        count_stmt = count_stmt.where(search_filter)
        stmt = stmt.where(search_filter)
    if is_active is not None:
        count_stmt = count_stmt.where(SqnsResource.is_active == is_active)
        stmt = stmt.where(SqnsResource.is_active == is_active)
    if active is not None:
        count_stmt = count_stmt.where(SqnsResource.active == active)
        stmt = stmt.where(SqnsResource.active == active)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(
        SqnsResource.is_active.desc(),
        SqnsResource.name,
    ).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    specialists: list[SqnsSpecialistListItem] = []
    for row in rows:
        resource = row[0]
        services_count = int(row[1] or 0)
        raw_data = resource.raw_data if isinstance(resource.raw_data, dict) else None
        specialist = SqnsSpecialistListItem.model_validate(
            {
                "id": resource.id,
                "external_id": resource.external_id,
                "name": resource.name,
                "role": resource.specialization,
                "email": _extract_raw_text(raw_data, ("email", "mail", "eMail")),
                "phone": _extract_raw_text(raw_data, ("phone", "mobile", "telephone")),
                "services_count": services_count,
                "linked_services": services_count,
                "is_active": resource.is_active,
                "active": resource.active,
                "information": resource.information,
            }
        )
        specialists.append(specialist)

    has_more = offset + len(specialists) < total
    current_page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return {
        "specialists": specialists,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "page": current_page,
        "pages": total_pages,
    }


@router.patch("/{agent_id}/sqns/specialists/{specialist_id}")
async def sqns_update_specialist(
    agent_id: UUID,
    specialist_id: UUID,
    payload: SqnsSpecialistUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Обновить поля специалиста для конкретного агента:
    - active: участвует ли специалист в подборе/записи
    - information: дополнительное описание
    """
    from sqlalchemy import func
    from app.db.models.sqns_service import SqnsResource, SqnsServiceResource

    agent = await get_agent_or_404(agent_id, db, user)

    stmt = select(SqnsResource).where(
        SqnsResource.id == specialist_id,
        SqnsResource.agent_id == agent.id,
    )
    specialist = (await db.execute(stmt)).scalar_one_or_none()

    if not specialist:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Specialist not found",
        )

    if payload.active is None and payload.information is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (active or information) must be provided",
        )

    if payload.active is not None:
        specialist.active = payload.active
    if payload.information is not None:
        information = payload.information.strip()
        specialist.information = information or None

    await db.commit()
    await db.refresh(specialist)

    raw_data = specialist.raw_data if isinstance(specialist.raw_data, dict) else None
    services_count_stmt = (
        select(func.count())
        .select_from(SqnsServiceResource)
        .where(SqnsServiceResource.resource_id == specialist.id)
    )
    services_count = int((await db.execute(services_count_stmt)).scalar() or 0)
    return SqnsSpecialistListItem.model_validate(
        {
            "id": specialist.id,
            "external_id": specialist.external_id,
            "name": specialist.name,
            "role": specialist.specialization,
            "email": _extract_raw_text(raw_data, ("email", "mail", "eMail")),
            "phone": _extract_raw_text(raw_data, ("phone", "mobile", "telephone")),
            "services_count": services_count,
            "linked_services": services_count,
            "is_active": specialist.is_active,
            "active": specialist.active,
            "information": specialist.information,
        }
    )


@router.get("/{agent_id}/sqns/slots")
async def sqns_slots(
    agent_id: UUID,
    resource_id: int = Query(...),
    date: str = Query(...),
    service_ids: list[int] = Query(..., alias="serviceIds"),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, Any]:
    agent = await get_agent_or_404(agent_id, db, user)
    client = await _build_sqns_client(agent, db, user)
    slots = await _execute_sqns_action(
        agent,
        db,
        client,
        lambda client: client.list_slots(resource_id, date, service_ids=service_ids),
    )
    return {"slots": slots}


@router.get("/{agent_id}/sqns/visits")
async def sqns_visits(
    agent_id: UUID,
    date_from: str = Query(...),
    date_till: str = Query(...),
    peer_page: int = Query(100, alias="peerPage"),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, Any]:
    agent = await get_agent_or_404(agent_id, db, user)
    client = await _build_sqns_client(agent, db, user)
    visits = await _execute_sqns_action(
        agent,
        db,
        client,
        lambda client: client.list_visits(date_from, date_till, peer_page=peer_page),
    )
    return {"visits": visits}


@router.get("/{agent_id}/sqns/client/{phone}")
async def sqns_client_by_phone(
    agent_id: UUID,
    phone: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict[str, Any]:
    agent = await get_agent_or_404(agent_id, db, user)
    client = await _build_sqns_client(agent, db, user)
    client_payload = await _execute_sqns_action(
        agent,
        db,
        client,
        lambda client: client.find_client_by_phone(phone),
    )
    return {"client": client_payload}


def _sqns_client_tags_list(raw: list | None) -> list[str] | None:
    if not raw:
        return None
    out: list[str] = []
    for t in raw:
        s = str(t).strip()
        if s:
            out.append(s)
    return out or None


def _strip_display_str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _compose_sqns_client_display_name(pii: dict[str, Any], raw: dict[str, Any] | None) -> str | None:
    """
    Полное имя для UI: фамилия, имя, отчество (как в SQNS), плюс запасные ключи в raw_data.
    Раньше в API отдавали только lastname из PII — из-за этого в списке была одна фамилия.
    """
    r = raw if isinstance(raw, dict) else {}
    last = _strip_display_str(
        pii.get("lastname") or r.get("lastname") or r.get("lastName"),
    )
    first = _strip_display_str(
        pii.get("firstname") or r.get("firstname") or r.get("firstName"),
    )
    pat = _strip_display_str(
        pii.get("patronymic") or r.get("patronymic") or r.get("middleName"),
    )
    parts = [p for p in (last, first, pat) if p]
    if parts:
        return " ".join(parts)
    return _strip_display_str(
        r.get("name")
        or r.get("fullName")
        or r.get("fio")
        or r.get("title")
        or r.get("displayName"),
    )


def _parse_external_exact(search: str) -> int | None:
    t = search.strip()
    if not t:
        return None
    up = t.upper()
    if up.startswith("PT-"):
        suffix = up[3:].strip()
        if suffix.isdigit():
            return int(suffix)
        return None
    if t.isdigit():
        return int(t)
    return None


def _sqns_client_row_matches_search(
    needle: str,
    rec: SqnsClientRecord,
    name_s: str | None,
    phone_s: str | None,
    tags: list[str] | None,
) -> bool:
    if not needle:
        return True
    n = needle.lower()
    if name_s and n in name_s.lower():
        return True
    if phone_s:
        pl = phone_s.lower()
        if n in pl:
            return True
        digits_p = "".join(c for c in phone_s if c.isdigit())
        digits_n = "".join(c for c in needle if c.isdigit())
        if digits_n and digits_n in digits_p:
            return True
    if n in str(rec.external_id):
        return True
    ext_ex = _parse_external_exact(needle)
    if ext_ex is not None and rec.external_id == ext_ex:
        return True
    ct = rec.client_type
    if isinstance(ct, str) and n in ct.lower():
        return True
    if tags:
        for tag in tags:
            if n in tag.lower():
                return True
    return False


def _sqns_clients_parse_tags_csv(tags_csv: str | None) -> list[str]:
    if not tags_csv or not str(tags_csv).strip():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for part in str(tags_csv).split(","):
        t = _normalize_text(part)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _sqns_clients_visits_channel_tag_filter(
    visits: list[Any],
    *,
    clients_by_external_id: dict[int, SqnsClientRecord],
    channel: str | None,
    tags_csv: str | None,
) -> list[Any]:
    """Те же правила канала/тегов, что в AgentAnalyticsService._build_view."""
    ch = (channel or "").strip()
    normalized_channel = _normalize_channel(ch) if ch else ""
    normalized_tags = set(_sqns_clients_parse_tags_csv(tags_csv))
    out: list[Any] = []
    for visit in visits:
        cid = int(visit.client_external_id) if visit.client_external_id is not None else None
        client = clients_by_external_id.get(cid) if cid is not None else None
        client_tags = _extract_client_tags(client)
        visit_channel = _extract_visit_channel(visit)
        if normalized_channel and visit_channel != normalized_channel:
            continue
        if normalized_tags and not client_tags.intersection(normalized_tags):
            continue
        out.append(visit)
    return out


def _parse_payment_client_external_id(value: str | None) -> int | None:
    normalized = _normalize_text(value)
    if not normalized:
        return None
    try:
        return int(normalized)
    except ValueError:
        return None


def _payments_for_patients_visit_cohort(
    payments: list[SqnsPayment],
    *,
    allowed_visit_ext_strs: frozenset[str],
    visit_client_by_ext: dict[str, int],
    allowed_client_ids: frozenset[int],
    normalized_channel: str,
    normalized_tags: set[str],
    clients_by_external_id: dict[int, SqnsClientRecord],
    revenue_basis: AnalyticsRevenueBasis,
    allowed_payment_methods: frozenset[str] | None,
    allowed_revenue_handles: frozenset[str] | None,
) -> list[SqnsPayment]:
    deduped = _dedupe_payments_for_revenue(payments)
    if revenue_basis == "clinical":
        deduped = [p for p in deduped if _payment_allowed_for_revenue_basis(p, revenue_basis)]
    if allowed_payment_methods:
        deduped = [
            p for p in deduped
            if _normalize_text(p.payment_method) in allowed_payment_methods
        ]
    if allowed_revenue_handles is not None:
        deduped = [
            p for p in deduped
            if (_normalize_text(p.payment_type_handle) or _normalize_text(p.payment_type_id) or "")
            in allowed_revenue_handles
        ]

    out: list[SqnsPayment] = []
    for payment in deduped:
        pay_vid = _normalize_text(payment.visit_external_id)
        if pay_vid and pay_vid in allowed_visit_ext_strs:
            out.append(payment)
            continue
        if normalized_channel:
            continue
        if normalized_tags:
            cid = _parse_payment_client_external_id(payment.client_external_id)
            if cid is None:
                continue
            client = clients_by_external_id.get(cid)
            if not client:
                continue
            tags = _extract_client_tags(client)
            if tags.intersection(normalized_tags):
                out.append(payment)
            continue
        cid = _parse_payment_client_external_id(payment.client_external_id)
        if cid is not None and cid in allowed_client_ids:
            out.append(payment)
    return out


@router.get("/{agent_id}/sqns/clients", response_model=SqnsClientsListResponse)
async def sqns_list_clients(
    agent_id: UUID,
    search: str | None = Query(None),
    client_type: str | None = Query(None),
    visit_date_from: date | None = Query(None, alias="vf"),
    visit_date_to: date | None = Query(None, alias="vt"),
    visit_cohort: str | None = Query(None, alias="vc"),
    slice_timezone: str | None = Query(
        None,
        alias="tz",
        description="IANA TZ как в аналитике; границы vf/vt интерпретируются в этой зоне.",
    ),
    channel: str | None = Query(None, description="Канал записи, как в аналитике"),
    tags: str | None = Query(None, description="Теги клиентов через запятую, как query tags в аналитике"),
    revenue_basis: AnalyticsRevenueBasis = Query(
        default="clinical",
        description="При непустом payment_methods: какие типы платежей учитывать (как в аналитике).",
    ),
    payment_methods: list[str] = Query(
        default_factory=list,
        alias="payment_methods",
        description="Фильтр по способу оплаты (cash, card, certificate). Пусто — срезовая выручка по сумме визита, как раньше.",
    ),
    revenue_categories: list[str] = Query(
        default_factory=list,
        alias="revenue_categories",
        description="services, commodities — тип оплаты SQNS. Вместе с payment_methods или отдельно включает расчёт по платежам.",
    ),
    resource_external_id: int | None = Query(
        None,
        alias="resource",
        description="Внешний ID сотрудника (SQNS); только визиты этого специалиста в срезе vf/vt/vc.",
    ),
    sort_by: str = Query("visits_count"),
    sort_order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> SqnsClientsListResponse:
    """
    Список кэшированных клиентов SQNS для страницы «Пациенты».
    Поиск по имени/телефону/типу/тегам/external_id выполняется после расшифровки PII в памяти.
    """
    from app.services.sqns.client_pii import decrypt_client_pii

    agent = await get_agent_or_404(agent_id, db, user)

    stmt = select(SqnsClientRecord).where(SqnsClientRecord.agent_id == agent.id)
    if client_type:
        stmt = stmt.where(SqnsClientRecord.client_type == client_type)

    result = await db.execute(stmt)
    records = list(result.scalars().all())

    needle = (search or "").strip()

    rows_work: list[dict[str, Any]] = []
    for rec in records:
        pii = decrypt_client_pii(rec.pii_data)
        raw_safe = rec.raw_data if isinstance(rec.raw_data, dict) else None
        name_s = _compose_sqns_client_display_name(pii, raw_safe)
        phone_raw = pii.get("phone")
        phone_s = str(phone_raw).strip() if phone_raw is not None else None
        if phone_s == "":
            phone_s = None
        birth_raw = pii.get("birthDate")
        birth_str = str(birth_raw) if birth_raw is not None else None

        client_tags = _sqns_client_tags_list(rec.tags if isinstance(rec.tags, list) else None)

        if not _sqns_client_row_matches_search(needle, rec, name_s, phone_s, client_tags):
            continue

        rows_work.append(
            {
                "record": rec,
                "name": name_s,
                "phone": phone_s,
                "birth": birth_str,
                "tags": client_tags,
            }
        )

    cohort_visits_for_revenue: list[Any] | None = None
    cohort_require_arrived_for_revenue = False
    cohort_revenue_from_payments = False
    slice_visit_count: int | None = None
    slice_revenue_by_client: dict[int, Decimal] = {}
    slice_visits_count_by_client: dict[int, int] = {}

    cohort_key = (visit_cohort or "").strip().lower()
    valid_cohorts = frozenset(
        {
            "primary_bookings",
            "primary_arrived",
            "repeat_bookings",
            "repeat_arrived",
            "all_bookings",
            "all_arrived",
        }
    )
    if (
        visit_date_from is not None
        and visit_date_to is not None
        and cohort_key in valid_cohorts
    ):
        from app.db.models.sqns_service import SqnsVisit

        tz_name = (slice_timezone or "").strip() or None
        period = build_analytics_period(
            date_from=visit_date_from,
            date_to=visit_date_to,
            timezone_name=tz_name,
            fallback_timezone=agent.timezone,
        )
        v_stmt = select(SqnsVisit).where(
            SqnsVisit.agent_id == agent.id,
            SqnsVisit.deleted.is_(False),
            SqnsVisit.visit_datetime.is_not(None),
            SqnsVisit.visit_datetime >= period.start_utc,
            SqnsVisit.visit_datetime < period.end_utc,
        )
        if cohort_key in ("primary_bookings", "primary_arrived"):
            v_stmt = v_stmt.where(SqnsVisit.is_primary_visit.is_(True))
        elif cohort_key in ("repeat_bookings", "repeat_arrived"):
            v_stmt = v_stmt.where(SqnsVisit.is_primary_visit.is_(False))

        if resource_external_id is not None:
            v_stmt = v_stmt.where(SqnsVisit.resource_external_id == resource_external_id)

        visits = list((await db.execute(v_stmt)).scalars().all())
        v_client_ids = {int(v.client_external_id) for v in visits if v.client_external_id is not None}
        clients_by_ext: dict[int, SqnsClientRecord] = {}
        if v_client_ids:
            c_stmt = select(SqnsClientRecord).where(
                SqnsClientRecord.agent_id == agent.id,
                SqnsClientRecord.external_id.in_(v_client_ids),
            )
            for crec in (await db.execute(c_stmt)).scalars().all():
                clients_by_ext[int(crec.external_id)] = crec

        visits = _sqns_clients_visits_channel_tag_filter(
            visits,
            clients_by_external_id=clients_by_ext,
            channel=channel,
            tags_csv=tags,
        )

        require_arrived = cohort_key.endswith("_arrived")
        cohort_visits_for_revenue = visits
        cohort_require_arrived_for_revenue = require_arrived

        normalized_channel = _normalize_channel(channel) if channel else ""
        normalized_tags: set[str] = set()
        if tags:
            for raw_item in str(tags).split(","):
                t = _normalize_text(raw_item)
                if t:
                    normalized_tags.add(t)

        allowed_pm = frozenset(_normalize_text(m) for m in payment_methods if _normalize_text(m))
        allow_rev_handles = resolve_revenue_category_handles(
            [c for c in revenue_categories if _normalize_text(c)]
        )
        use_payment_slice = bool(allowed_pm) or (allow_rev_handles is not None)

        allowed_external: set[int] = set()
        allowed_visit_ext_strs: set[str] = set()
        visit_client_by_ext: dict[str, int] = {}
        slice_visit_count = 0
        for v in visits:
            cid = v.client_external_id
            if cid is None:
                continue
            if require_arrived and not is_sqns_visit_arrived(v):
                continue
            slice_visit_count += 1
            cid_int = int(cid)
            allowed_external.add(cid_int)
            vext = str(v.external_id)
            allowed_visit_ext_strs.add(vext)
            visit_client_by_ext[vext] = cid_int
            if not use_payment_slice:
                amt = v.total_cost if v.total_cost is not None else v.total_price
                if amt is not None:
                    slice_revenue_by_client[cid_int] = slice_revenue_by_client.get(cid_int, Decimal("0")) + amt
            slice_visits_count_by_client[cid_int] = slice_visits_count_by_client.get(cid_int, 0) + 1

        if use_payment_slice:
            cohort_revenue_from_payments = True
            pay_stmt = select(SqnsPayment).where(
                SqnsPayment.agent_id == agent.id,
                SqnsPayment.payment_date.is_not(None),
                SqnsPayment.payment_date >= period.start_utc,
                SqnsPayment.payment_date < period.end_utc,
            )
            raw_payments = list((await db.execute(pay_stmt)).scalars().all())
            filtered_pay = _payments_for_patients_visit_cohort(
                raw_payments,
                allowed_visit_ext_strs=frozenset(allowed_visit_ext_strs),
                visit_client_by_ext=visit_client_by_ext,
                allowed_client_ids=frozenset(allowed_external),
                normalized_channel=normalized_channel,
                normalized_tags=normalized_tags,
                clients_by_external_id=clients_by_ext,
                revenue_basis=revenue_basis,
                allowed_payment_methods=allowed_pm if allowed_pm else None,
                allowed_revenue_handles=allow_rev_handles,
            )
            for p in filtered_pay:
                amt = p.amount
                if amt is None:
                    continue
                pay_vid = _normalize_text(p.visit_external_id)
                cid_int: int | None
                if pay_vid and pay_vid in visit_client_by_ext:
                    cid_int = visit_client_by_ext[pay_vid]
                else:
                    cid_int = _parse_payment_client_external_id(p.client_external_id)
                if cid_int is None or cid_int not in allowed_external:
                    continue
                slice_revenue_by_client[cid_int] = slice_revenue_by_client.get(cid_int, Decimal("0")) + amt

        rows_work = [
            row for row in rows_work if int(row["record"].external_id) in allowed_external
        ]

    allowed_sort = {"visits_count", "total_arrival", "synced_at", "external_id"}
    if sort_by not in allowed_sort:
        sort_by = "visits_count"
    reverse = sort_order.lower() != "asc"

    def sort_key(row: dict[str, Any]) -> Any:
        r = row["record"]
        if sort_by == "visits_count":
            return r.visits_count if r.visits_count is not None else -1
        if sort_by == "total_arrival":
            return float(r.total_arrival) if r.total_arrival is not None else -1.0
        if sort_by == "synced_at":
            return r.synced_at.timestamp()
        return r.external_id

    rows_work.sort(key=sort_key, reverse=reverse)

    total = len(rows_work)
    visits_count_sum = sum(int(row["record"].visits_count or 0) for row in rows_work)

    revenue_total = Decimal("0")
    if cohort_visits_for_revenue is not None:
        if cohort_revenue_from_payments:
            revenue_total = sum(slice_revenue_by_client.values(), start=Decimal("0"))
        else:
            for v in cohort_visits_for_revenue:
                cid = v.client_external_id
                if cid is None:
                    continue
                if cohort_require_arrived_for_revenue and not is_sqns_visit_arrived(v):
                    continue
                amt = v.total_cost if v.total_cost is not None else v.total_price
                if amt is not None:
                    revenue_total += amt
    else:
        for row in rows_work:
            ta = row["record"].total_arrival
            if ta is not None:
                revenue_total += ta

    total_arrival_sum = Decimal("0")
    for row in rows_work:
        ta = row["record"].total_arrival
        if ta is not None:
            total_arrival_sum += ta

    from app.db.models.sqns_service import SqnsResource, SqnsVisit
    from app.services.sqns.mcp_server import _extract_resource_name, _extract_service_name

    last_visit_total_price_sum = Decimal("0")
    all_sel_external_ids = [int(row["record"].external_id) for row in rows_work]
    if all_sel_external_ids:
        now_dt = datetime.now(timezone.utc)
        visit_chunk = 2000
        for i in range(0, len(all_sel_external_ids), visit_chunk):
            chunk = all_sel_external_ids[i : i + visit_chunk]
            all_visits_totals_stmt = (
                select(SqnsVisit)
                .where(
                    SqnsVisit.agent_id == agent.id,
                    SqnsVisit.client_external_id.in_(chunk),
                    SqnsVisit.deleted.is_(False),
                    SqnsVisit.visit_datetime.is_not(None),
                )
                .order_by(SqnsVisit.visit_datetime)
            )
            all_visits_tot = list((await db.execute(all_visits_totals_stmt)).scalars().all())
            by_client: dict[int, list[Any]] = {}
            for v in all_visits_tot:
                cex = v.client_external_id
                if cex is not None:
                    by_client.setdefault(int(cex), []).append(v)
            for cid in chunk:
                vlist = by_client.get(cid, [])
                upcoming = [v for v in vlist if v.visit_datetime >= now_dt]
                past_arrived = [v for v in vlist if v.visit_datetime < now_dt and is_sqns_visit_arrived(v)]
                pick = upcoming[0] if upcoming else (past_arrived[-1] if past_arrived else None)
                if pick is not None and pick.total_price is not None:
                    last_visit_total_price_sum += pick.total_price

    filtered_external_ids = [row["record"].external_id for row in rows_work]
    top_service_name: str | None = None
    top_service_bookings: int | None = None
    if filtered_external_ids:
        service_counts: Counter[str] = Counter()
        chunk_size = 2000
        for i in range(0, len(filtered_external_ids), chunk_size):
            chunk = filtered_external_ids[i : i + chunk_size]
            visits_for_top_stmt = select(SqnsVisit).where(
                SqnsVisit.agent_id == agent.id,
                SqnsVisit.client_external_id.in_(chunk),
                SqnsVisit.deleted.is_(False),
            )
            for v in (await db.execute(visits_for_top_stmt)).scalars().all():
                if not is_sqns_visit_arrived(v):
                    continue
                raw = v.raw_data if isinstance(v.raw_data, dict) else {}
                svc = _extract_service_name(raw)
                if svc:
                    service_counts[svc] += 1
        if service_counts:
            top_service_name, top_bookings = service_counts.most_common(1)[0]
            top_service_bookings = int(top_bookings)

    page = rows_work[offset : offset + limit]

    # Bulk-загрузка визитов для всей страницы одним запросом
    page_external_ids = [row["record"].external_id for row in page]
    visit_by_client: dict[int, Any] = {}
    if page_external_ids:
        all_visits_stmt = (
            select(SqnsVisit)
            .where(
                SqnsVisit.agent_id == agent.id,
                SqnsVisit.client_external_id.in_(page_external_ids),
                SqnsVisit.deleted.is_(False),
                SqnsVisit.visit_datetime.is_not(None),
            )
            .order_by(SqnsVisit.visit_datetime)
        )
        all_visits = list((await db.execute(all_visits_stmt)).scalars().all())

        # Для каждого клиента: берём ближайший будущий визит, иначе последний прошедший
        now_dt = datetime.now(timezone.utc)
        tmp: dict[int, list[Any]] = {}
        for v in all_visits:
            cid = v.client_external_id
            if cid is not None:
                tmp.setdefault(cid, []).append(v)
        for cid, vlist in tmp.items():
            upcoming = [v for v in vlist if v.visit_datetime >= now_dt]
            past_arrived = [v for v in vlist if v.visit_datetime < now_dt and is_sqns_visit_arrived(v)]
            visit_by_client[cid] = upcoming[0] if upcoming else (past_arrived[-1] if past_arrived else None)

        # Bulk-загрузка специалистов для найденных визитов
        res_ids = {
            v.resource_external_id
            for v in visit_by_client.values()
            if v is not None and v.resource_external_id is not None
        }
        name_by_res: dict[int, str] = {}
        if res_ids:
            r_stmt = select(SqnsResource.external_id, SqnsResource.name).where(
                SqnsResource.agent_id == agent.id,
                SqnsResource.external_id.in_(res_ids),
            )
            for ext_id, rname in (await db.execute(r_stmt)).all():
                if ext_id is not None:
                    name_by_res[int(ext_id)] = str(rname)
    else:
        name_by_res = {}

    clients: list[SqnsClientListItem] = []
    for row in page:
        rec = row["record"]
        v = visit_by_client.get(rec.external_id)

        last_visit_dt = None
        last_svc = None
        last_spec = None
        last_visit_total_price = None

        if v:
            last_visit_dt = v.visit_datetime
            last_visit_total_price = v.total_price
            raw = v.raw_data if isinstance(v.raw_data, dict) else {}
            last_svc = _extract_service_name(raw)
            if v.resource_external_id is not None:
                last_spec = name_by_res.get(int(v.resource_external_id))
            if not last_spec:
                last_spec = _extract_resource_name(raw, None)

        ext_id_int = int(rec.external_id)
        clients.append(
            SqnsClientListItem(
                id=rec.id,
                external_id=rec.external_id,
                name=row["name"],
                phone=row["phone"],
                birth_date=row["birth"],
                sex=rec.sex,
                client_type=rec.client_type,
                visits_count=rec.visits_count,
                total_arrival=rec.total_arrival,
                tags=row["tags"],
                last_visit_datetime=last_visit_dt,
                last_service_name=last_svc,
                last_specialist_name=last_spec,
                last_visit_total_price=last_visit_total_price,
                slice_revenue=slice_revenue_by_client.get(ext_id_int),
                slice_visits_count=slice_visits_count_by_client.get(ext_id_int),
                synced_at=rec.synced_at,
            )
        )

    has_more = offset + len(clients) < total
    return SqnsClientsListResponse(
        clients=clients,
        total=total,
        limit=limit,
        offset=offset,
        has_more=has_more,
        revenue_total=revenue_total,
        total_arrival_sum=total_arrival_sum,
        visits_count_sum=visits_count_sum,
        last_visit_total_price_sum=last_visit_total_price_sum,
        slice_visit_count=slice_visit_count,
        top_service_name=top_service_name,
        top_service_bookings=top_service_bookings,
    )


async def _sqns_cached_visits_response_for_client(
    *,
    db: AsyncSession,
    agent: Agent,
    client_rec: SqnsClientRecord,
    limit: int,
) -> SqnsClientCachedVisitsResponse:
    from app.db.models.sqns_service import SqnsResource, SqnsVisit
    from app.services.sqns.mcp_server import _extract_resource_name, _extract_service_name
    from app.services.sqns.visit_arrival import is_sqns_visit_arrived

    v_stmt = (
        select(SqnsVisit)
        .where(
            SqnsVisit.agent_id == agent.id,
            SqnsVisit.client_external_id == client_rec.external_id,
            SqnsVisit.deleted.is_(False),
        )
        .order_by(nulls_last(desc(SqnsVisit.visit_datetime)))
        .limit(limit)
    )
    visits = list((await db.execute(v_stmt)).scalars().all())

    res_ids = {v.resource_external_id for v in visits if v.resource_external_id is not None}
    name_by_res: dict[int, str] = {}
    if res_ids:
        r_stmt = select(SqnsResource.external_id, SqnsResource.name).where(
            SqnsResource.agent_id == agent.id,
            SqnsResource.external_id.in_(res_ids),
        )
        for ext_id, name in (await db.execute(r_stmt)).all():
            if ext_id is not None and name is not None:
                name_by_res[int(ext_id)] = str(name)

    out: list[SqnsClientCachedVisitItem] = []
    for v in visits:
        raw = v.raw_data if isinstance(v.raw_data, dict) else {}
        svc = _extract_service_name(raw)
        spec: str | None = None
        if v.resource_external_id is not None:
            spec = name_by_res.get(int(v.resource_external_id))
        if not spec:
            spec = _extract_resource_name(raw, None)
        out.append(
            SqnsClientCachedVisitItem(
                id=v.id,
                visit_external_id=v.external_id,
                visit_datetime=v.visit_datetime,
                visit_datetime_raw=sqns_visit_datetime_raw_string(raw),
                service_name=svc,
                specialist_name=spec,
                attendance=v.attendance,
                arrived=is_sqns_visit_arrived(v),
                total_price=v.total_price,
            )
        )

    return SqnsClientCachedVisitsResponse(visits=out)


@router.get(
    "/{agent_id}/sqns/clients/by-external/{external_client_id:int}/visits",
    response_model=SqnsClientCachedVisitsResponse,
)
async def sqns_client_cached_visits_by_external(
    agent_id: UUID,
    external_client_id: int,
    limit: int = Query(40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> SqnsClientCachedVisitsResponse:
    """
    Визиты пациента по SQNS external_id клиента (надёжнее UUID записи в БД для UI).
    """
    agent = await get_agent_or_404(agent_id, db, user)
    cr_stmt = select(SqnsClientRecord).where(
        SqnsClientRecord.external_id == external_client_id,
        SqnsClientRecord.agent_id == agent.id,
    )
    client_rec = (await db.execute(cr_stmt)).scalar_one_or_none()
    if client_rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client not found")
    return await _sqns_cached_visits_response_for_client(
        db=db, agent=agent, client_rec=client_rec, limit=limit
    )


@router.get(
    "/{agent_id}/sqns/clients/{client_record_id}/visits",
    response_model=SqnsClientCachedVisitsResponse,
)
async def sqns_client_cached_visits(
    agent_id: UUID,
    client_record_id: UUID,
    limit: int = Query(40, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> SqnsClientCachedVisitsResponse:
    """
    Визиты пациента из локального кэша sqns_visits (после синхронизации).
    """
    agent = await get_agent_or_404(agent_id, db, user)

    cr_stmt = select(SqnsClientRecord).where(
        SqnsClientRecord.id == client_record_id,
        SqnsClientRecord.agent_id == agent.id,
    )
    client_rec = (await db.execute(cr_stmt)).scalar_one_or_none()
    if client_rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client not found")

    return await _sqns_cached_visits_response_for_client(
        db=db, agent=agent, client_rec=client_rec, limit=limit
    )


# ============================================================================
# Управление кэшем SQNS
# ============================================================================


@router.post("/{agent_id}/sqns/sync")
async def sqns_sync_services(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Ручная синхронизация данных SQNS в локальный кэш.

    Выполняет:
    1. Синхронизацию сотрудников и проекции специалистов
    2. Синхронизацию услуг, категорий и связей услуга-специалист
    3. Синхронизацию товаров
    4. Синхронизацию визитов
    5. Синхронизацию платежей
    """
    agent = await get_agent_or_404(agent_id, db, user)

    if not agent.sqns_enabled or not agent.sqns_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SQNS integration is not enabled for this agent",
        )

    sqns_client = await _build_sqns_client(agent, db, user)
    async with sqns_agent_lock(agent.id) as acquired:
        if not acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SQNS synchronization is already running for this agent",
            )
        sync_result = await sync_sqns_entities(
            db=db,
            sqns_client=sqns_client,
            agent_id=agent.id,
            trigger="manual",
        )

    if sync_result.success:
        agent.sqns_last_sync_at = sync_result.synced_at
        agent.sqns_last_activity_at = sync_result.synced_at
        agent.sqns_status = "ok"
        agent.sqns_error = None
        await db.commit()
        await db.refresh(agent)
    else:
        agent.sqns_status = "error"
        agent.sqns_error = sync_result.message[:2000]
        agent.sqns_last_activity_at = datetime.utcnow()
        await db.commit()
        await db.refresh(agent)

    return sync_result


@router.get("/{agent_id}/sqns/services/cached")
async def sqns_list_cached_services(
    agent_id: UUID,
    search: str | None = None,
    category: str | None = None,
    is_enabled: bool | None = None,
    limit: int = Query(100, ge=1, le=1000, description="Максимум результатов (1-1000)"),
    offset: int = Query(0, ge=0, description="Смещение для пагинации"),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Получить список услуг из кэша с фильтрацией для управления на frontend.

    Query Parameters:
    - search: поиск по названию/описанию (ILIKE)
    - category: фильтр по категории
    - is_enabled: фильтр по статусу (включена/отключена)
    - limit: максимум результатов (1-1000)
    - offset: смещение для пагинации
    """
    from sqlalchemy import func, select
    from app.db.models.sqns_service import SqnsService, SqnsServiceResource
    from app.schemas.sqns_service import SqnsServiceListItem

    agent = await get_agent_or_404(agent_id, db, user)

    # Базовый запрос для подсчета total (без join'ов)
    count_stmt = select(func.count(SqnsService.id)).where(SqnsService.agent_id == agent.id)

    # Запрос с join'ами для данных
    stmt = (
        select(
            SqnsService,
            func.count(SqnsServiceResource.id).label("specialists_count"),
        )
        .outerjoin(
            SqnsServiceResource,
            SqnsServiceResource.service_id == SqnsService.id,
        )
        .where(SqnsService.agent_id == agent.id)
        .group_by(SqnsService.id)
    )

    # Применяем фильтры к обоим запросам
    if search:
        search_filter = (
            SqnsService.name.ilike(f"%{search}%")
            | SqnsService.description.ilike(f"%{search}%")
        )
        count_stmt = count_stmt.where(search_filter)
        stmt = stmt.where(search_filter)
    if category:
        count_stmt = count_stmt.where(SqnsService.category == category)
        stmt = stmt.where(SqnsService.category == category)
    if is_enabled is not None:
        count_stmt = count_stmt.where(SqnsService.is_enabled == is_enabled)
        stmt = stmt.where(SqnsService.is_enabled == is_enabled)

    # Считаем total до пагинации
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Сортировка и пагинация
    stmt = stmt.order_by(
        SqnsService.priority.desc(),
        SqnsService.name,
    ).limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows = result.all()

    services = []
    for row in rows:
        service_data = row[0]
        specialists_count = row[1]
        price_range = _extract_price_range(service_data.raw_data)

        service_dict = {
            "id": service_data.id,
            "external_id": service_data.external_id,
            "name": service_data.name,
            "category": service_data.category,
            "price": service_data.price,
            "duration_seconds": service_data.duration_seconds,
            "is_enabled": service_data.is_enabled,
            "priority": service_data.priority,
            "specialists_count": specialists_count,
            "price_range": price_range,
        }
        services.append(SqnsServiceListItem.model_validate(service_dict))

    # Рассчитываем данные для пагинации
    has_more = offset + len(services) < total
    current_page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = (total + limit - 1) // limit if limit > 0 else 1

    return {
        "services": services,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "page": current_page,
        "pages": total_pages,
    }


@router.get("/{agent_id}/sqns/service-employee-links")
async def sqns_list_service_employee_links(
    agent_id: UUID,
    limit: int = Query(5000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Плоский список связей услуга-сотрудник для отображения в таблице "Все записи".
    Источник: sqns_service_resources (JOIN sqns_services + sqns_resources).
    Услуги без сотрудников также включаются (employee = null).
    """
    from sqlalchemy import func, select
    from app.db.models.sqns_service import SqnsResource, SqnsService, SqnsServiceResource

    agent = await get_agent_or_404(agent_id, db, user)

    # Все связи из link-таблицы
    links_stmt = (
        select(
            SqnsService.id.label("service_id"),
            SqnsService.name.label("service_name"),
            SqnsService.category.label("category_name"),
            SqnsService.updated_at.label("service_updated_at"),
            SqnsResource.id.label("resource_id"),
            SqnsResource.name.label("employee_name"),
            SqnsResource.updated_at.label("resource_updated_at"),
            SqnsServiceResource.updated_at.label("link_updated_at"),
            SqnsServiceResource.created_at.label("link_created_at"),
        )
        .join(SqnsService, SqnsService.id == SqnsServiceResource.service_id)
        .join(SqnsResource, SqnsResource.id == SqnsServiceResource.resource_id)
        .where(SqnsService.agent_id == agent.id)
        .order_by(SqnsService.name, SqnsResource.name)
    )
    link_rows = (await db.execute(links_stmt)).all()

    # Услуги, у которых есть хотя бы одна связь
    linked_service_ids: set = {row.service_id for row in link_rows}

    all_items: list[dict[str, Any]] = []
    for row in link_rows:
        updated_at = max(
            (dt for dt in [row.link_updated_at, row.service_updated_at, row.resource_updated_at, row.link_created_at] if dt is not None),
            default=None,
        )
        all_items.append({
            "service": row.service_name,
            "employee": row.employee_name,
            "category": row.category_name,
            "updated_at": updated_at,
        })

    # Услуги без сотрудников
    orphan_stmt = (
        select(
            SqnsService.name.label("service_name"),
            SqnsService.category.label("category_name"),
            SqnsService.updated_at.label("service_updated_at"),
        )
        .where(
            SqnsService.agent_id == agent.id,
            SqnsService.id.notin_(linked_service_ids) if linked_service_ids else True,
        )
        .order_by(SqnsService.name)
    )
    orphan_rows = (await db.execute(orphan_stmt)).all()
    for row in orphan_rows:
        all_items.append({
            "service": row.service_name,
            "employee": None,
            "category": row.category_name,
            "updated_at": row.service_updated_at,
        })

    total = len(all_items)
    items = all_items[offset: offset + limit]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


@router.patch("/{agent_id}/sqns/services/{service_id}")
async def sqns_update_service(
    agent_id: UUID,
    service_id: UUID,
    payload: SqnsServiceUpdate | None = Body(None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Обновить настройки одной услуги (is_enabled, priority).
    """
    from app.db.models.sqns_service import SqnsService

    agent = await get_agent_or_404(agent_id, db, user)

    stmt = select(SqnsService).where(
        SqnsService.id == service_id,
        SqnsService.agent_id == agent.id,
    )
    service = (await db.execute(stmt)).scalar_one_or_none()

    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    if payload is None:
        payload = SqnsServiceUpdate(is_enabled=not service.is_enabled)

    if payload.is_enabled is not None:
        service.is_enabled = payload.is_enabled
    if payload.priority is not None:
        service.priority = payload.priority

    await db.commit()
    await db.refresh(service)

    return SqnsServiceRead.model_validate(service)


@router.post("/{agent_id}/sqns/services/bulk-update")
async def sqns_bulk_update_services(
    agent_id: UUID,
    payload: SqnsServiceBulkUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Массовое обновление услуг (включить/отключить, изменить приоритет).
    """
    from sqlalchemy import update
    from app.db.models.sqns_service import SqnsService

    agent = await get_agent_or_404(agent_id, db, user)

    if not payload.service_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="service_ids list cannot be empty",
        )

    update_values = {}
    if payload.is_enabled is not None:
        update_values["is_enabled"] = payload.is_enabled
    if payload.priority is not None:
        update_values["priority"] = payload.priority

    if not update_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update",
        )

    stmt = (
        update(SqnsService)
        .where(
            SqnsService.id.in_(payload.service_ids),
            SqnsService.agent_id == agent.id,
        )
        .values(**update_values)
    )

    result = await db.execute(stmt)
    await db.commit()

    return {
        "updated_count": result.rowcount,
        "message": f"Successfully updated {result.rowcount} services",
    }


@router.get("/{agent_id}/sqns/categories")
async def sqns_list_categories(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Получить список категорий услуг с настройками.
    """
    from sqlalchemy import func, select
    from app.db.models.sqns_service import SqnsServiceCategory, SqnsService

    agent = await get_agent_or_404(agent_id, db, user)

    stmt = (
        select(
            SqnsServiceCategory,
            func.count(SqnsService.id).label("services_count"),
        )
        .outerjoin(
            SqnsService,
            (SqnsService.agent_id == SqnsServiceCategory.agent_id)
            & (SqnsService.category == SqnsServiceCategory.name),
        )
        .where(SqnsServiceCategory.agent_id == agent.id)
        .group_by(SqnsServiceCategory.id)
        .order_by(
            SqnsServiceCategory.priority.desc(),
            SqnsServiceCategory.name,
        )
    )

    result = await db.execute(stmt)
    rows = result.all()

    categories = []
    for row in rows:
        category_data = row[0]
        services_count = row[1]

        category_dict = {
            "id": category_data.id,
            "agent_id": category_data.agent_id,
            "name": category_data.name,
            "is_enabled": category_data.is_enabled,
            "priority": category_data.priority,
            "created_at": category_data.created_at,
            "updated_at": category_data.updated_at,
            "services_count": services_count,
        }
        categories.append(SqnsCategoryRead.model_validate(category_dict))

    return {"categories": categories}


@router.patch("/{agent_id}/sqns/categories/{category_id}")
async def sqns_update_category(
    agent_id: UUID,
    category_id: UUID,
    payload: SqnsCategoryUpdate | None = Body(None),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Обновить настройки категории (is_enabled, priority).
    """
    from app.db.models.sqns_service import SqnsServiceCategory

    agent = await get_agent_or_404(agent_id, db, user)

    stmt = select(SqnsServiceCategory).where(
        SqnsServiceCategory.id == category_id,
        SqnsServiceCategory.agent_id == agent.id,
    )
    category = (await db.execute(stmt)).scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is required",
        )

    # Проверяем, что хотя бы одно поле передано для обновления
    if payload.is_enabled is None and payload.priority is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (is_enabled or priority) must be provided",
        )

    if payload.is_enabled is not None:
        category.is_enabled = payload.is_enabled
    if payload.priority is not None:
        category.priority = payload.priority

    await db.commit()
    await db.refresh(category)

    return SqnsCategoryRead.model_validate(category)


@router.get("/{agent_id}/sqns/disable-preview")
async def sqns_disable_preview(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
):
    """
    Предпросмотр данных, которые будут удалены при отключении SQNS.
    """
    from sqlalchemy import func, select
    from app.db.models.sqns_service import (
        SqnsClientRecord,
        SqnsCommodity,
        SqnsEmployee,
        SqnsPayment,
        SqnsResource,
        SqnsService,
        SqnsServiceResource,
        SqnsServiceCategory,
        SqnsSyncCursor,
        SqnsSyncRun,
        SqnsVisit,
    )

    agent = await get_agent_or_404(agent_id, db, user)

    # Считаем специалистов
    resources_stmt = select(func.count(SqnsResource.id)).where(
        SqnsResource.agent_id == agent.id
    )
    resources_count = (await db.execute(resources_stmt)).scalar() or 0

    # Считаем услуги
    services_stmt = select(func.count(SqnsService.id)).where(
        SqnsService.agent_id == agent.id
    )
    services_count = (await db.execute(services_stmt)).scalar() or 0

    # Считаем связи
    links_stmt = (
        select(func.count(SqnsServiceResource.id))
        .join(SqnsService, SqnsServiceResource.service_id == SqnsService.id)
        .where(SqnsService.agent_id == agent.id)
    )
    links_count = (await db.execute(links_stmt)).scalar() or 0

    # Считаем категории
    categories_stmt = select(func.count(SqnsServiceCategory.id)).where(
        SqnsServiceCategory.agent_id == agent.id
    )
    categories_count = (await db.execute(categories_stmt)).scalar() or 0

    commodities_stmt = select(func.count(SqnsCommodity.id)).where(
        SqnsCommodity.agent_id == agent.id
    )
    commodities_count = (await db.execute(commodities_stmt)).scalar() or 0

    employees_stmt = select(func.count(SqnsEmployee.id)).where(
        SqnsEmployee.agent_id == agent.id
    )
    employees_count = (await db.execute(employees_stmt)).scalar() or 0

    clients_stmt = select(func.count(SqnsClientRecord.id)).where(
        SqnsClientRecord.agent_id == agent.id
    )
    clients_count = (await db.execute(clients_stmt)).scalar() or 0

    visits_stmt = select(func.count(SqnsVisit.id)).where(
        SqnsVisit.agent_id == agent.id
    )
    visits_count = (await db.execute(visits_stmt)).scalar() or 0

    payments_stmt = select(func.count(SqnsPayment.id)).where(
        SqnsPayment.agent_id == agent.id
    )
    payments_count = (await db.execute(payments_stmt)).scalar() or 0

    cursor_stmt = select(func.count(SqnsSyncCursor.id)).where(
        SqnsSyncCursor.agent_id == agent.id
    )
    cursor_count = (await db.execute(cursor_stmt)).scalar() or 0

    runs_stmt = select(func.count(SqnsSyncRun.id)).where(
        SqnsSyncRun.agent_id == agent.id
    )
    runs_count = (await db.execute(runs_stmt)).scalar() or 0

    return {
        "will_be_deleted": {
            "resources": resources_count,
            "services": services_count,
            "service_resource_links": links_count,
            "categories": categories_count,
            "commodities": commodities_count,
            "employees": employees_count,
            "clients": clients_count,
            "visits": visits_count,
            "payments": payments_count,
            "sync_cursor": cursor_count,
            "sync_runs": runs_count,
        },
        "warning": "Все эти данные будут удалены без возможности восстановления при отключении SQNS.",
    }
