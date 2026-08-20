"""Помощник-конструктор: чат, который подсказывает, как собрать агента.

Эндпоинт только читает конфигурацию агента и отвечает текстом с карточками
переходов. Создание функций, сценариев и таблиц остаётся за человеком —
помощник ничего не сохраняет.
"""
from __future__ import annotations

import time
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.agent_assistant import AssistantChatRequest, AssistantChatResponse
from app.schemas.auth import AuthContext
from app.services.agent_assistant import (
    build_activity_snapshot,
    build_agent_snapshot,
    render_activity,
    render_snapshot,
    run_assistant,
    sanitize_actions,
)
from app.services.agent_assistant.dialogs import load_recent_dialogs, render_dialogs
from app.services.agent_assistant.service import AssistantRunResult, AssistantTools
from app.services.runtime.model_resolver import provider_prefix_from_model_name
from app.services.tenant_balance import apply_balance_charge
from app.services.tenant_llm_config import get_decrypted_api_key
from app.services.token_costing import apply_fallback_costs

logger = structlog.get_logger(__name__)

# Промпты бывают на десять тысяч символов — в ответ инструмента отдаём
# ограниченный кусок, иначе один вызов съест весь контекст.
PROMPT_TEXT_LIMIT = 12000

router = APIRouter()


def _normalize_model(model: str | None) -> str | None:
    """Отсечь пустышки. Swagger UI подставляет литерал "string" в необязательные поля."""
    if model is None:
        return None
    normalized = model.strip()
    if not normalized or normalized == "string":
        return None
    return normalized


def _build_tools(db: AsyncSession, agent) -> AssistantTools:
    """Инструменты помощника, привязанные к текущему агенту.

    Сессия живёт до конца запроса, а инструменты вызываются внутри него —
    закрывать её вручную не нужно. Ошибку каждого инструмента возвращаем
    текстом: упавший инструмент не должен ронять весь ответ.
    """

    async def read_prompt() -> str:
        text = (agent.system_prompt or "").strip()
        if not text:
            return "Системный промпт пуст."
        return text[:PROMPT_TEXT_LIMIT]

    async def read_activity(days: int = 30) -> str:
        try:
            snapshot = await build_activity_snapshot(db, agent=agent, days=max(1, min(days, 90)))
            return render_activity(snapshot)
        except Exception as exc:  # noqa: BLE001
            logger.warning("assistant_tool_activity_failed", agent_id=str(agent.id), error=str(exc))
            return "Не удалось получить статистику работы агента."

    async def read_dialogs(limit: int = 3) -> str:
        try:
            dialogs = await load_recent_dialogs(db, agent=agent, limit=limit)
            return render_dialogs(dialogs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("assistant_tool_dialogs_failed", agent_id=str(agent.id), error=str(exc))
            return "Не удалось получить диалоги агента."

    return AssistantTools(
        read_prompt=read_prompt, read_activity=read_activity, read_dialogs=read_dialogs
    )


def _describe_page(payload: AssistantChatRequest) -> str | None:
    """Человекочитаемое «где сейчас пользователь» для промпта."""
    title = (payload.page_title or "").strip()
    path = (payload.page_path or "").strip()
    if title and path:
        return f"«{title}» ({path})"
    return title or path or None


async def _charge_tenant(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    result: AssistantRunResult,
) -> None:
    """Списать стоимость консультации с баланса организации.

    Помощник — такой же расход токенов, как запуск агента, и он должен быть
    виден в балансе. Сбой списания не должен ломать уже полученный ответ:
    пользователь свой ответ увидит, а мы увидим предупреждение в логах.
    """
    if not result.token_usage_steps:
        return
    try:
        cost_usd, _cost_rub = await apply_fallback_costs(
            db, token_usage_steps=result.token_usage_steps
        )
        if cost_usd is None or cost_usd <= 0:
            return
        await apply_balance_charge(
            db,
            tenant_id=tenant_id,
            amount_usd=cost_usd,
            source_type="agent_assistant",
            source_id=f"{agent_id}:{int(time.time() * 1000)}",
            metadata={"model": result.model_name},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent_assistant_billing_failed",
            agent_id=str(agent_id),
            model=result.model_name,
            error=str(exc),
        )


@router.post(
    "/assistant/chat",
    response_model=AssistantChatResponse,
    summary="Спросить помощника по конструктору агента",
)
async def assistant_chat(
    agent_id: UUID,
    payload: AssistantChatRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> AssistantChatResponse:
    agent = await get_agent_or_404(agent_id, db, user)

    settings = get_settings()
    # Своя настройка, не pydanticai_default_model: та задаёт модель всем агентам
    # в рантайме, и переключать её ради помощника нельзя.
    effective_model = _normalize_model(payload.model) or settings.agent_assistant_model

    # resolve_model «падает открыто»: без ключа тенанта он вернёт строку, и
    # PydanticAI уедет на переменные окружения платформы. Поэтому ключ
    # проверяем здесь, до вызова.
    openai_api_key = await get_decrypted_api_key(db, agent.tenant_id, "openai")
    anthropic_api_key = await get_decrypted_api_key(db, agent.tenant_id, "anthropic")
    provider = provider_prefix_from_model_name(effective_model) or "openai"
    if provider == "anthropic" and not anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "API-ключ Anthropic не настроен для организации. "
                "Установите его в Настройках организации → Ключи LLM."
            ),
        )
    if provider == "openai" and not openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "API-ключ OpenAI не настроен для организации. "
                "Установите его в Настройках организации → Ключи LLM."
            ),
        )

    snapshot = await build_agent_snapshot(db, agent=agent)
    snapshot_text = render_snapshot(snapshot)

    try:
        result = await run_assistant(
            question=payload.message,
            history=payload.history,
            snapshot_text=snapshot_text,
            actions=sanitize_actions(payload.actions),
            function_presets=payload.function_presets,
            scenario_presets=payload.scenario_presets,
            model_name=effective_model,
            page=_describe_page(payload),
            tools=_build_tools(db, agent),
            reasoning_effort=settings.agent_assistant_reasoning_effort,
            openai_api_key=openai_api_key,
            anthropic_api_key=anthropic_api_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "agent_assistant_failed",
            agent_id=str(agent.id),
            model=effective_model,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Помощник временно недоступен, попробуйте ещё раз",
        ) from exc

    await _charge_tenant(db, tenant_id=agent.tenant_id, agent_id=agent.id, result=result)

    return AssistantChatResponse(
        message=result.output.message,
        suggestions=result.output.suggestions,
        followups=result.output.followups,
        model=result.model_name,
    )
