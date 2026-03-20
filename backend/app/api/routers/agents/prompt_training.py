"""Эндпоинты для обучения промпта через диалог с мета-агентом."""
from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.prompt_training import (
    GeneratedPromptPreview,
    GeneratePromptRequest,
    TrainingFeedbackCreate,
    TrainingFeedbackRead,
    TrainingSessionCreate,
    TrainingSessionListItem,
    TrainingSessionListResponse,
    TrainingSessionRead,
)
from sqlalchemy import exists, select

from app.db.models.binding import AgentToolBinding
from app.db.models.function_rule import FunctionRule
from app.db.models.tool import Tool
from app.services.audit import write_audit
from app.services.prompt_trainer import ToolInfo, generate_improved_prompt
from app.services.tenant_llm_config import get_decrypted_api_key
from app.services.prompt_training_crud import (
    add_feedback,
    cancel_session,
    complete_session,
    create_session,
    get_session,
    get_session_feedbacks,
    get_session_with_feedbacks,
    list_sessions,
)
from app.services.system_prompt_history import create_version

logger = structlog.get_logger(__name__)

router = APIRouter()


def _normalize_meta_model(model: str | None) -> str | None:
    """Normalize known invalid UI placeholder model values."""
    if model is None:
        return None
    normalized = model.strip()
    if not normalized or normalized == "string":
        return None
    return normalized


async def _load_agent_tools(db: AsyncSession, agent_id: UUID, tenant_id: UUID) -> list[ToolInfo]:
    """Загрузить описания инструментов агента для контекста мета-агента."""
    bindings_stmt = select(AgentToolBinding.tool_id).where(
        AgentToolBinding.agent_id == agent_id,
        AgentToolBinding.tenant_id == tenant_id,
    )
    tool_ids = (await db.execute(bindings_stmt)).scalars().all()
    if not tool_ids:
        return []

    tools_stmt = select(Tool).where(
        Tool.id.in_(tool_ids),
        Tool.tenant_id == tenant_id,
        Tool.is_deleted.is_(False),
        Tool.status == "active",
        exists(
            select(FunctionRule.id).where(
                FunctionRule.tenant_id == tenant_id,
                FunctionRule.agent_id == agent_id,
                FunctionRule.tool_id == Tool.id,
                FunctionRule.enabled.is_(True),
            )
        ) | (Tool.execution_type != "internal"),
    )
    tools = (await db.execute(tools_stmt)).scalars().all()

    result: list[ToolInfo] = []
    for t in tools:
        # Legacy rows may contain non-object input_schema; avoid 500 in prompt training.
        parameters = t.input_schema if isinstance(t.input_schema, dict) else None
        result.append(
            ToolInfo(
                name=t.name,
                description=t.description or "",
                parameters=parameters,
            )
        )
    return result


@router.post(
    "/prompt-training/sessions",
    response_model=TrainingSessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать тренировочную сессию",
)
async def create_training_session(
    agent_id: UUID,
    payload: TrainingSessionCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> TrainingSessionRead:
    agent = await get_agent_or_404(agent_id, db, user)

    meta_model = _normalize_meta_model(payload.meta_model) or get_settings().pydanticai_default_model
    session = await create_session(db, agent, user, meta_model=meta_model)
    await db.commit()

    await write_audit(
        db,
        user,
        "agent.prompt_training.create_session",
        "prompt_training_session",
        str(session.id),
        metadata={"agent_id": str(agent.id), "meta_model": meta_model},
    )

    session = await get_session_with_feedbacks(db, session.id, agent.id, agent.tenant_id)
    data = TrainingSessionRead.model_validate(session)
    data.agent_model = agent.model
    return data


@router.post(
    "/prompt-training/sessions/{session_id}/feedback",
    response_model=TrainingFeedbackRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить коррекцию / фидбек",
)
async def add_training_feedback(
    agent_id: UUID,
    session_id: UUID,
    payload: TrainingFeedbackCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> TrainingFeedbackRead:
    agent = await get_agent_or_404(agent_id, db, user)
    session = await get_session(db, session_id, agent.id, agent.tenant_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training session not found",
        )
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Training session is {session.status}, cannot add feedback",
        )

    fb = await add_feedback(db, session, payload)
    await db.commit()
    await db.refresh(fb)

    return TrainingFeedbackRead.model_validate(fb)


@router.post(
    "/prompt-training/sessions/{session_id}/generate",
    response_model=GeneratedPromptPreview,
    summary="Сгенерировать улучшенный промпт",
)
async def generate_prompt(
    agent_id: UUID,
    session_id: UUID,
    payload: GeneratePromptRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> GeneratedPromptPreview:
    agent = await get_agent_or_404(agent_id, db, user)
    session = await get_session(db, session_id, agent.id, agent.tenant_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training session not found",
        )
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Training session is {session.status}, cannot generate",
        )

    feedbacks = await get_session_feedbacks(db, session.id)
    if not feedbacks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No feedback provided yet — add at least one correction",
        )

    effective_model = (
        _normalize_meta_model(payload.meta_model) if payload else None
    ) or _normalize_meta_model(session.meta_model) or get_settings().pydanticai_default_model

    if effective_model != session.meta_model:
        session.meta_model = effective_model

    agent_tools = await _load_agent_tools(db, agent.id, agent.tenant_id)
    openai_api_key = await get_decrypted_api_key(db, agent.tenant_id)

    if not openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="API-ключ OpenAI не настроен для организации. Установите его в Настройках организации → Ключ LLM.",
        )

    try:
        result = await generate_improved_prompt(
            current_prompt=agent.system_prompt or "",
            feedbacks=feedbacks,
            meta_model=effective_model,
            tools=agent_tools or None,
            openai_api_key=openai_api_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "prompt_generate_failed",
            session_id=str(session.id),
            agent_id=str(agent.id),
            meta_model=effective_model,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Prompt generation failed due to upstream model error",
        ) from exc

    session.generated_prompt = result.system_prompt
    session.generated_prompt_reasoning = result.reasoning
    await db.commit()

    logger.info(
        "prompt_generated_via_api",
        session_id=str(session.id),
        agent_id=str(agent.id),
        meta_model=effective_model,
        feedback_count=len(feedbacks),
    )

    return GeneratedPromptPreview(
        current_prompt=agent.system_prompt or "",
        generated_prompt=result.system_prompt,
        reasoning=result.reasoning,
        change_summary=result.change_summary,
        feedback_used=len(feedbacks),
        meta_model=effective_model,
        agent_model=agent.model,
    )


@router.post(
    "/prompt-training/sessions/{session_id}/apply",
    response_model=TrainingSessionRead,
    summary="Применить сгенерированный промпт",
)
async def apply_generated_prompt(
    agent_id: UUID,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> TrainingSessionRead:
    agent = await get_agent_or_404(agent_id, db, user)
    session = await get_session_with_feedbacks(db, session_id, agent.id, agent.tenant_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training session not found",
        )
    if not session.generated_prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No generated prompt — call /generate first",
        )
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Training session is {session.status}, cannot apply",
        )

    version = await create_version(
        db,
        agent,
        system_prompt=session.generated_prompt,
        user=user,
        change_summary=f"AI training: {session.generated_prompt_reasoning[:200] if session.generated_prompt_reasoning else 'auto-generated'}",
        triggered_by="ai_training",
        activate=True,
    )

    await complete_session(db, session, generated_version_id=version.id)
    await db.commit()

    await write_audit(
        db,
        user,
        "agent.prompt_training.apply",
        "prompt_training_session",
        str(session.id),
        metadata={
            "agent_id": str(agent.id),
            "version_id": str(version.id),
            "version_number": version.version_number,
        },
    )

    logger.info(
        "prompt_applied_via_training",
        session_id=str(session.id),
        agent_id=str(agent.id),
        version_number=version.version_number,
    )

    session = await get_session_with_feedbacks(db, session.id, agent.id, agent.tenant_id)
    data = TrainingSessionRead.model_validate(session)
    data.agent_model = agent.model
    return data


@router.get(
    "/prompt-training/sessions",
    response_model=TrainingSessionListResponse,
    summary="Список тренировочных сессий",
)
async def list_training_sessions(
    agent_id: UUID,
    limit: int = Query(default=30, ge=1, le=100),
    cursor: UUID | None = Query(default=None, description="ID последней загруженной сессии"),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> TrainingSessionListResponse:
    agent = await get_agent_or_404(agent_id, db, user)

    sessions = await list_sessions(
        db, agent.id, agent.tenant_id, limit=limit + 1, cursor_id=cursor,
    )

    has_more = len(sessions) > limit
    if has_more:
        sessions = sessions[:limit]

    items = [TrainingSessionListItem.model_validate(s) for s in sessions]
    next_cursor = str(items[-1].id) if has_more and items else None

    return TrainingSessionListResponse(items=items, next_cursor=next_cursor)


@router.get(
    "/prompt-training/sessions/{session_id}",
    response_model=TrainingSessionRead,
    summary="Детали тренировочной сессии",
)
async def get_training_session(
    agent_id: UUID,
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> TrainingSessionRead:
    agent = await get_agent_or_404(agent_id, db, user)
    session = await get_session_with_feedbacks(db, session_id, agent.id, agent.tenant_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training session not found",
        )

    data = TrainingSessionRead.model_validate(session)
    data.agent_model = agent.model
    return data
