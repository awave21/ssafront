from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_scope
from app.db.models.agent import Agent
from app.db.models.run import Run
from app.db.session import get_db
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate
from app.services.runtime.default_agent_prompt import build_default_agent_system_prompt
from app.services.runtime.diagnose_tool import DIAGNOSE_PROMPT_BRIDGE
from app.services.runtime.script_flow_tool import SCRIPT_FLOWS_PROMPT_BRIDGE
from app.services.sqns.tool_texts import SQNS_PROMPT_BRIDGE
from app.schemas.auth import AuthContext
from app.services.audit import write_audit

from app.api.routers.agents.deps import get_agent_or_404
from app.services.system_prompt_history import create_version

logger = structlog.get_logger()

router = APIRouter()
ZERO_COST = Decimal("0")


async def _load_agent_cost_totals(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_ids: list[UUID],
) -> dict[UUID, tuple[Decimal, Decimal]]:
    if not agent_ids:
        return {}

    stmt = (
        select(
            Run.agent_id,
            func.coalesce(func.sum(Run.cost_usd), 0).label("total_cost_usd"),
            func.coalesce(func.sum(Run.cost_rub), 0).label("total_cost_rub"),
        )
        .where(
            Run.tenant_id == tenant_id,
            Run.agent_id.in_(agent_ids),
        )
        .group_by(Run.agent_id)
    )
    result = await db.execute(stmt)

    totals: dict[UUID, tuple[Decimal, Decimal]] = {}
    for row in result.all():
        totals[row.agent_id] = (
            row.total_cost_usd if row.total_cost_usd is not None else ZERO_COST,
            row.total_cost_rub if row.total_cost_rub is not None else ZERO_COST,
        )
    return totals


def _build_agent_read(agent: Agent, totals: dict[UUID, tuple[Decimal, Decimal]]) -> AgentRead:
    total_cost_usd, total_cost_rub = totals.get(agent.id, (ZERO_COST, ZERO_COST))
    return AgentRead.model_validate(agent).model_copy(
        update={
            "total_cost_usd": total_cost_usd,
            "total_cost_rub": total_cost_rub,
        }
    )


async def _build_agent_read_single(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent: Agent,
) -> AgentRead:
    totals = await _load_agent_cost_totals(
        db,
        tenant_id=tenant_id,
        agent_ids=[agent.id],
    )
    return _build_agent_read(agent, totals)


@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    payload: AgentCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentRead:
    llm_params = payload.llm_params
    if isinstance(llm_params, BaseModel):
        llm_params = llm_params.model_dump(exclude_none=True)

    resolved_prompt = (payload.system_prompt or "").strip()
    if not resolved_prompt:
        resolved_prompt = build_default_agent_system_prompt()

    agent = Agent(
        tenant_id=user.tenant_id,
        owner_user_id=user.user_id,
        name=payload.name,
        system_prompt=resolved_prompt,
        model=payload.model,
        llm_params=llm_params,
        status=payload.status,
        version=payload.version,
        knowledge_tool_description=payload.knowledge_tool_description,
    )
    db.add(agent)
    await db.flush()  # получить agent.id до коммита

    # Сохраняем начальную версию системного промпта
    if resolved_prompt:
        await create_version(
            db,
            agent,
            system_prompt=resolved_prompt,
            user=user,
            change_summary="Начальная версия",
            triggered_by="create",
            activate=True,
        )

    await db.commit()
    await db.refresh(agent)
    await write_audit(db, user, "agent.create", "agent", str(agent.id))
    return await _build_agent_read_single(db, tenant_id=user.tenant_id, agent=agent)


class DefaultSystemPromptResponse(BaseModel):
    """Стартовый системный промпт с оркестровкой инструментов (режим manual)."""

    system_prompt: str
    note: str = (
        "Шаблон по умолчанию: диагностика мотива, экспертные потоки, запись через SQNS "
        "(раздел SQNS можно удалить, если интеграция не используется)."
    )


@router.get("/defaults/system-prompt", response_model=DefaultSystemPromptResponse)
async def get_default_system_prompt(
    user: AuthContext = Depends(require_scope("agents:read")),
) -> DefaultSystemPromptResponse:
    """Текст для поля system_prompt при создании агента — видимый, редактируемый в UI."""
    _ = user
    return DefaultSystemPromptResponse(system_prompt=build_default_agent_system_prompt())


@router.get("", response_model=list[AgentRead])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
    limit: int = 50,
    offset: int = 0,
) -> list[AgentRead]:
    logger.info("list_agents_called", tenant_id=str(user.tenant_id), limit=limit, offset=offset)
    try:
        stmt = (
            select(Agent)
            .where(Agent.tenant_id == user.tenant_id, Agent.is_deleted.is_(False))
            .order_by(Agent.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        agents = result.scalars().all()
        totals = await _load_agent_cost_totals(
            db,
            tenant_id=user.tenant_id,
            agent_ids=[agent.id for agent in agents],
        )
        logger.info("list_agents_success", tenant_id=str(user.tenant_id), count=len(agents))
        return [_build_agent_read(agent, totals) for agent in agents]
    except Exception as e:
        logger.error("list_agents_error", tenant_id=str(user.tenant_id), error=str(e), error_type=type(e).__name__)
        raise


@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> AgentRead:
    agent = await get_agent_or_404(agent_id, db, user)
    return await _build_agent_read_single(db, tenant_id=user.tenant_id, agent=agent)


@router.put("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentRead:
    agent = await get_agent_or_404(agent_id, db, user)
    old_is_disabled = agent.is_disabled

    update_data = payload.model_dump(exclude_unset=True)

    # Проверяем, изменился ли system_prompt — если да, создаём версию
    new_prompt = update_data.get("system_prompt")
    prompt_changed = new_prompt is not None and new_prompt != agent.system_prompt

    for key, value in update_data.items():
        setattr(agent, key, value)

    if prompt_changed:
        await create_version(
            db,
            agent,
            system_prompt=new_prompt,
            user=user,
            change_summary=None,
            triggered_by="update",
            activate=True,
        )

    await db.commit()
    await db.refresh(agent)
    await write_audit(db, user, "agent.update", "agent", str(agent.id))
    if old_is_disabled != agent.is_disabled:
        await write_audit(
            db,
            user,
            "agent.disable.toggle",
            "agent",
            str(agent.id),
            metadata={
                "old_value": old_is_disabled,
                "new_value": agent.is_disabled,
            },
        )
    return await _build_agent_read_single(db, tenant_id=user.tenant_id, agent=agent)


@router.post("/{agent_id}/publish", response_model=AgentRead)
async def publish_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AgentRead:
    agent = await get_agent_or_404(agent_id, db, user)

    agent.status = "published"

    # Создаём снимок текущего промпта при публикации
    await create_version(
        db,
        agent,
        system_prompt=agent.system_prompt,
        user=user,
        change_summary="Публикация агента",
        triggered_by="publish",
        activate=True,
    )

    await db.commit()
    await db.refresh(agent)
    await write_audit(db, user, "agent.publish", "agent", str(agent.id))
    return await _build_agent_read_single(db, tenant_id=user.tenant_id, agent=agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    agent = await get_agent_or_404(agent_id, db, user)

    agent.is_deleted = True
    agent.deleted_at = datetime.utcnow()
    await db.commit()
    await write_audit(db, user, "agent.delete", "agent", str(agent.id))
    return None


class RuntimeBridgeItem(BaseModel):
    key: str
    title: str
    description: str
    prompt_text: str


class RuntimeBridgesResponse(BaseModel):
    mode: str
    bridges: list[RuntimeBridgeItem]


@router.get("/{agent_id}/runtime-bridges", response_model=RuntimeBridgesResponse)
async def get_runtime_bridges(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> RuntimeBridgesResponse:
    """Возвращает тексты оркестровочных инструкций (bridge-блоки), которые runtime
    автоматически добавляет к системному промпту агента в режиме 'auto'.

    Используй этот эндпоинт в UI чтобы:
    - показать пользователю что именно добавляется скрыто
    - предложить скопировать нужные блоки в системный промпт при переключении на 'manual'
    """
    agent = await get_agent_or_404(agent_id, db, user)
    mode = getattr(agent, "runtime_bridges_mode", "auto") or "auto"

    bridges = [
        RuntimeBridgeItem(
            key="diagnose",
            title="Диагностика мотива клиента",
            description=(
                "Инструкция когда вызывать diagnose_client_motive и как интерпретировать результат. "
                "Активна если у агента есть Мотивы/Возражения в Knowledge Graph."
            ),
            prompt_text=DIAGNOSE_PROMPT_BRIDGE,
        ),
        RuntimeBridgeItem(
            key="script_flows",
            title="Экспертные сценарии (потоки)",
            description=(
                "Инструкция когда вызывать search_script_flows и как применять результат "
                "(communication_style, preferred_phrases, required_followup_question). "
                "Активна если у агента есть проиндексированные потоки."
            ),
            prompt_text=SCRIPT_FLOWS_PROMPT_BRIDGE,
        ),
        RuntimeBridgeItem(
            key="sqns",
            title="Запись клиентов (SQNS)",
            description=(
                "Пошаговая оркестровка записи, переноса и отмены визитов через SQNS-инструменты. "
                "Активна если у агента включён SQNS."
            ),
            prompt_text=SQNS_PROMPT_BRIDGE,
        ),
    ]

    return RuntimeBridgesResponse(mode=mode, bridges=bridges)
