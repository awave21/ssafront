from __future__ import annotations

import structlog
import json
import os
import time
from uuid import UUID, uuid4
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.db.models.dialog_state import DialogState
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.dialog import DialogRead, DialogStatusUpdate
from app.services.dialog_state import set_dialog_status
from app.utils.message_mapping import extract_user_info

logger = structlog.get_logger(__name__)

router = APIRouter()

@router.get("/debug/all-runs")
async def debug_all_runs(
    db: AsyncSession = Depends(get_db),
):
    """
    DEBUG: Получить вообще все записи из таблицы runs.
    """
    # region agent log
    try:
        os.makedirs("/opt/app-agent/myapp/backend/.cursor", exist_ok=True)
        with open("/opt/app-agent/myapp/backend/.cursor/debug-e26c68.log", "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e26c68",
                "runId": "audit-1",
                "hypothesisId": "H2",
                "location": "app/api/routers/agents/dialogs.py:debug_all_runs",
                "message": "debug_all_runs_called",
                "data": {},
                "timestamp": int(time.time() * 1000),
            }) + "\n")
    except Exception:
        pass
    # endregion agent log
    stmt = select(Run).order_by(Run.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    runs = result.scalars().all()
    
    return [
        {
            "id": str(r.id),
            "agent_id": str(r.agent_id),
            "session_id": r.session_id,
            "tenant_id": str(r.tenant_id),
            "input": r.input_message,
            "created_at": r.created_at.isoformat()
        }
        for r in runs
    ]

@router.get("")
async def list_dialogs(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:read")),
):
    """
    Получить список диалогов (сессий) для конкретного агента.
    """
    logger.info("list_dialogs_request", agent_id=str(agent_id), user_tenant=str(user.tenant_id))
    
    # Фильтруем по agent_id. 
    # Убираем фильтр по tenant_id для самих ранов, так как вебхуки могут создавать 
    # раны под системным тенантом, но менеджер должен их видеть.
    stmt = (
        select(
            Run.session_id,
            func.max(Run.created_at).label("last_message_at"),
        )
        .where(
            Run.agent_id == agent_id,
        )
        .group_by(Run.session_id)
        .order_by(func.max(Run.created_at).desc())
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    logger.info("list_dialogs_found", count=len(rows))
    
    # Собираем все session_id, чтобы одним запросом получить статусы
    session_ids = [row[0] for row in rows]
    status_map: dict[str, str] = {}
    if session_ids:
        state_stmt = (
            select(DialogState.session_id, DialogState.status)
            .where(
                DialogState.agent_id == agent_id,
                DialogState.session_id.in_(session_ids),
            )
        )
        state_rows = (await db.execute(state_stmt)).all()
        status_map = {r[0]: r[1] for r in state_rows}
    
    dialogs = []
    for row in rows:
        session_id = row[0]
        
        # Для каждого session_id найдем последний input_message для заголовка
        last_run_stmt = (
            select(Run.input_message)
            .where(Run.session_id == session_id)
            .order_by(Run.created_at.desc())
            .limit(1)
        )
        last_message = (await db.execute(last_run_stmt)).scalar() or "Новый диалог"
        
        # Извлекаем user_info из сообщений сессии.
        # Ищем первое сообщение с user_info от конечного пользователя (не менеджера),
        # чтобы получить реальные данные Telegram (username, first_name, last_name).
        user_info = None
        user_info_stmt = (
            select(SessionMessage.message)
            .where(SessionMessage.session_id == session_id)
            .order_by(SessionMessage.message_index.asc())
            .limit(20)
        )
        user_info_rows = (await db.execute(user_info_stmt)).scalars().all()
        
        fallback_user_info = None
        for msg in user_info_rows:
            if not isinstance(msg, dict):
                continue
            extracted = extract_user_info(msg)
            if not extracted:
                continue
            # Предпочитаем user_info от конечного пользователя (telegram, whatsapp и т.д.),
            # а не от менеджера — у менеджера нет username/first_name.
            if extracted.get("platform") not in ("manager",):
                user_info = extracted
                break
            # Сохраняем manager user_info как fallback на случай, если другого нет
            if fallback_user_info is None:
                fallback_user_info = extracted
        
        if not user_info:
            user_info = fallback_user_info
        
        # Fallback: формируем базовый user_info из session_id для Telegram
        if not user_info and session_id.startswith("telegram:"):
            user_info = {
                "platform": "telegram",
                "platform_id": session_id.split(":")[1],
                "session_id": session_id,
            }
        
        # Реальный статус из dialog_states (если нет записи — active)
        dialog_status = status_map.get(session_id, "active")
        
        dialogs.append(
            {
                "id": session_id,
                "agent_id": str(agent_id),
                "title": last_message[:50] + ("..." if len(last_message) > 50 else ""),
                "last_message_preview": last_message[:100],
                "last_message_at": row[1].isoformat() if hasattr(row[1], 'isoformat') else str(row[1]),
                "unread_count": 0,
                "is_pinned": False,
                "status": dialog_status,
                "user_info": user_info,
            }
        )
    
    # Возвращаем объект, который ожидает фронтенд: { "dialogs": [...] }
    return {"dialogs": dialogs}

@router.post("", response_model=DialogRead)
async def create_dialog(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:write")),
) -> DialogRead:
    """
    Создать новый диалог (просто генерирует новый session_id).
    """
    await get_agent_or_404(agent_id, db, user)
    
    new_session_id = str(uuid4())
    
    return DialogRead(
        id=new_session_id,
        agent_id=agent_id,
        title="Новый диалог",
        last_message_preview=None,
        last_message_at=datetime.utcnow(),
        unread_count=0,
        is_pinned=False,
        status="active",
    )


@router.patch("/{dialog_id}/status")
async def update_dialog_status(
    agent_id: UUID,
    dialog_id: str,
    payload: DialogStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:write")),
):
    """
    Изменить статус диалога (active / paused / disabled).

    Если записи DialogState ещё нет — создаёт. Иначе обновляет.
    """
    await get_agent_or_404(agent_id, db, user)

    await set_dialog_status(
        db,
        agent_id=agent_id,
        tenant_id=user.tenant_id,
        session_id=dialog_id,
        new_status=payload.status,
    )

    return {"dialog_id": dialog_id, "status": payload.status}


@router.delete("/{dialog_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dialog(
    agent_id: UUID,
    dialog_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:delete")),
) -> None:
    """
    Удалить диалог и всю его историю.
    """
    await get_agent_or_404(agent_id, db, user)
    
    # Удаляем состояние диалога
    await db.execute(
        delete(DialogState).where(
            DialogState.session_id == dialog_id,
            DialogState.agent_id == agent_id,
        )
    )
    
    # Удаляем сообщения
    await db.execute(
        delete(SessionMessage).where(
            SessionMessage.session_id == dialog_id,
            SessionMessage.tenant_id == user.tenant_id
        )
    )
    
    # Удаляем раны
    await db.execute(
        delete(Run).where(
            Run.session_id == dialog_id,
            Run.tenant_id == user.tenant_id,
            Run.agent_id == agent_id
        )
    )
    
    await db.commit()
    return None
