from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.direct_question import DirectQuestion
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.direct_question import (
    DirectQuestionCreate,
    DirectQuestionRead,
    DirectQuestionToggle,
    DirectQuestionUpdate,
)
from app.services.direct_questions import (
    create_direct_question,
    delete_direct_question,
    list_direct_questions,
    reembed_agent_direct_questions,
    update_direct_question,
)

router = APIRouter()


def _api_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": code,
            "message": message,
            "detail": message,
            "field_errors": None,
        },
    )


async def _get_question_or_404(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    question_id: UUID,
) -> DirectQuestion:
    stmt = select(DirectQuestion).where(
        DirectQuestion.id == question_id,
        DirectQuestion.tenant_id == tenant_id,
        DirectQuestion.agent_id == agent_id,
    ).options(selectinload(DirectQuestion.files))
    question = (await db.execute(stmt)).scalar_one_or_none()
    if question is None:
        raise _api_error("not_found", "Direct question not found", status.HTTP_404_NOT_FOUND)
    return question


@router.get("", response_model=list[DirectQuestionRead])
async def get_direct_questions(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[DirectQuestionRead]:
    await get_agent_or_404(agent_id, db, user)
    questions = await list_direct_questions(db, tenant_id=user.tenant_id, agent_id=agent_id)
    return [DirectQuestionRead.model_validate(question) for question in questions]


@router.post("", response_model=DirectQuestionRead, status_code=status.HTTP_201_CREATED)
async def post_direct_question(
    agent_id: UUID,
    payload: DirectQuestionCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> DirectQuestionRead:
    await get_agent_or_404(agent_id, db, user)
    question = await create_direct_question(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        payload=payload,
    )
    return DirectQuestionRead.model_validate(question)


@router.put("/{direct_question_id}", response_model=DirectQuestionRead)
async def put_direct_question(
    agent_id: UUID,
    direct_question_id: UUID,
    payload: DirectQuestionUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> DirectQuestionRead:
    await get_agent_or_404(agent_id, db, user)
    question = await _get_question_or_404(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        question_id=direct_question_id,
    )
    updated = await update_direct_question(
        db,
        question=question,
        tenant_id=user.tenant_id,
        payload=payload,
    )
    return DirectQuestionRead.model_validate(updated)


@router.delete("/{direct_question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_direct_question(
    agent_id: UUID,
    direct_question_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await get_agent_or_404(agent_id, db, user)
    question = await _get_question_or_404(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        question_id=direct_question_id,
    )
    await delete_direct_question(db, question=question)


@router.post("/reembed", status_code=status.HTTP_200_OK)
async def post_reembed_direct_questions(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Принудительно пересчитать embeddings для всех прямых вопросов агента."""
    await get_agent_or_404(agent_id, db, user)
    result = await reembed_agent_direct_questions(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
    )
    return result


@router.patch("/{direct_question_id}/toggle", response_model=DirectQuestionRead)
async def patch_direct_question_toggle(
    agent_id: UUID,
    direct_question_id: UUID,
    payload: DirectQuestionToggle,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> DirectQuestionRead:
    await get_agent_or_404(agent_id, db, user)
    question = await _get_question_or_404(
        db,
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        question_id=direct_question_id,
    )
    question.is_enabled = payload.is_enabled
    await db.commit()
    await db.refresh(question)
    return DirectQuestionRead.model_validate(question)


