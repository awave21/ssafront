"""CRUD-операции для тренировочных сессий и фидбека."""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.agent import Agent
from app.db.models.prompt_training_feedback import PromptTrainingFeedback
from app.db.models.prompt_training_session import PromptTrainingSession
from app.schemas.auth import AuthContext
from app.schemas.prompt_training import TrainingFeedbackCreate

logger = structlog.get_logger(__name__)


async def create_session(
    db: AsyncSession,
    agent: Agent,
    user: AuthContext,
    meta_model: str = "openai:gpt-4.1",
) -> PromptTrainingSession:
    """Создать новую тренировочную сессию для агента."""
    session = PromptTrainingSession(
        agent_id=agent.id,
        tenant_id=agent.tenant_id,
        created_by=user.user_id,
        status="active",
        base_prompt_version=agent.version,
        meta_model=meta_model,
    )
    db.add(session)
    await db.flush()

    logger.info(
        "training_session_created",
        session_id=str(session.id),
        agent_id=str(agent.id),
        base_version=agent.version,
        meta_model=meta_model,
    )
    return session


async def add_feedback(
    db: AsyncSession,
    session: PromptTrainingSession,
    payload: TrainingFeedbackCreate,
) -> PromptTrainingFeedback:
    """Добавить фидбек в тренировочную сессию."""
    next_index_stmt = (
        select(func.coalesce(func.max(PromptTrainingFeedback.order_index), 0))
        .where(PromptTrainingFeedback.training_session_id == session.id)
    )
    result = await db.execute(next_index_stmt)
    next_index = result.scalar_one() + 1

    feedback = PromptTrainingFeedback(
        training_session_id=session.id,
        tenant_id=session.tenant_id,
        run_id=payload.run_id,
        feedback_type=payload.feedback_type,
        agent_response=payload.agent_response,
        correction_text=payload.correction_text,
        order_index=next_index,
    )
    db.add(feedback)

    session.feedback_count = next_index
    await db.flush()

    logger.info(
        "training_feedback_added",
        session_id=str(session.id),
        feedback_type=payload.feedback_type,
        order_index=next_index,
    )
    return feedback


async def get_session(
    db: AsyncSession,
    session_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
) -> PromptTrainingSession | None:
    """Получить тренировочную сессию по ID (без фидбеков)."""
    stmt = select(PromptTrainingSession).where(
        PromptTrainingSession.id == session_id,
        PromptTrainingSession.agent_id == agent_id,
        PromptTrainingSession.tenant_id == tenant_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_session_with_feedbacks(
    db: AsyncSession,
    session_id: UUID,
    agent_id: UUID,
    tenant_id: UUID,
) -> PromptTrainingSession | None:
    """Получить тренировочную сессию с загруженными фидбеками."""
    stmt = (
        select(PromptTrainingSession)
        .options(selectinload(PromptTrainingSession.feedbacks))
        .where(
            PromptTrainingSession.id == session_id,
            PromptTrainingSession.agent_id == agent_id,
            PromptTrainingSession.tenant_id == tenant_id,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    *,
    limit: int = 30,
    cursor_id: UUID | None = None,
) -> list[PromptTrainingSession]:
    """Список тренировочных сессий (от новых к старым) с курсорной пагинацией."""
    stmt = (
        select(PromptTrainingSession)
        .where(
            PromptTrainingSession.agent_id == agent_id,
            PromptTrainingSession.tenant_id == tenant_id,
        )
    )
    if cursor_id is not None:
        cursor_session = await db.get(PromptTrainingSession, cursor_id)
        if cursor_session:
            stmt = stmt.where(
                PromptTrainingSession.created_at < cursor_session.created_at,
            )

    stmt = stmt.order_by(PromptTrainingSession.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_session_feedbacks(
    db: AsyncSession,
    session_id: UUID,
) -> list[PromptTrainingFeedback]:
    """Получить все фидбеки сессии, отсортированные по order_index."""
    stmt = (
        select(PromptTrainingFeedback)
        .where(PromptTrainingFeedback.training_session_id == session_id)
        .order_by(PromptTrainingFeedback.order_index)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def complete_session(
    db: AsyncSession,
    session: PromptTrainingSession,
    generated_version_id: UUID,
) -> PromptTrainingSession:
    """Завершить тренировочную сессию после применения промпта."""
    session.status = "completed"
    session.generated_version_id = generated_version_id
    await db.flush()

    logger.info(
        "training_session_completed",
        session_id=str(session.id),
        generated_version_id=str(generated_version_id),
    )
    return session


async def cancel_session(
    db: AsyncSession,
    session: PromptTrainingSession,
) -> PromptTrainingSession:
    """Отменить тренировочную сессию."""
    session.status = "cancelled"
    await db.flush()

    logger.info(
        "training_session_cancelled",
        session_id=str(session.id),
    )
    return session
