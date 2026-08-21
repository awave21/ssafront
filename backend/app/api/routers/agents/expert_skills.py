"""Навыки эксперта — самостоятельная сущность (expert_skills), отделённая от потоков.

Навык это дистиллированный/написанный опыт по услуге (skill_doc), который правится
в чате/структуре и публикуется для рантайма (навык-слой + тул use_expert_skill).
НЕ связан жёстко с граф-потоком: дистилляция из потока — разовый импорт (копируем
skill_doc, ссылки не храним). Удаление мягкое (корзина + восстановление).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import require_scope
from app.api.routers.agents.deps import get_agent_or_404
from app.core.config import get_settings
from app.db.models.expert_skill import ExpertSkill
from app.db.models.script_flow import ScriptFlow
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.services.script_flow_skill_distiller import (
    distill_skill,
    converse_skill,
    converse_skill_stream,
    _sanitize_skill_doc,
)
from app.services.tenant_llm_config import get_decrypted_api_key

import structlog

logger = structlog.get_logger(__name__)

router = APIRouter()


def _api_error(code: str, message: str, http_status: int) -> HTTPException:
    return HTTPException(
        status_code=http_status,
        detail={"error": code, "message": message, "detail": message, "field_errors": None},
    )


# ── Schemas ───────────────────────────────────────────────────────────────────


class ExpertSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    name: str
    service_external_ids: list[str] = []
    skill_doc: dict[str, Any] | None = None
    status: str
    is_deleted: bool = False
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ExpertSkillCreate(BaseModel):
    name: str
    service_external_ids: list[str] = []
    # Разовый импорт: если задан — дистиллируем skill_doc из compiled_text этого
    # потока (ссылка не сохраняется, навык дальше живёт сам по себе).
    import_from_flow_id: UUID | None = None


class ExpertSkillUpdate(BaseModel):
    name: str | None = None
    service_external_ids: list[str] | None = None
    status: str | None = None


class SkillDocPatch(BaseModel):
    skill_doc: dict[str, Any]


class SkillChatMessage(BaseModel):
    role: str
    content: str


class SkillChatAttachment(BaseModel):
    name: str
    text: str


class SkillChatBody(BaseModel):
    messages: list[SkillChatMessage] = []
    attachments: list[SkillChatAttachment] = []
    skill_doc: dict[str, Any] | None = None
    model: str | None = None


class ReviewCorrectionBody(BaseModel):
    situation: str
    trigger_when: str = ""
    approach: str = ""
    phrase: str | None = None
    level: str = "пример"
    mark: str | None = None


class ImportFromFlowBody(BaseModel):
    flow_id: UUID


# Модели для ассистента навыка (белый список).
SKILL_CHAT_MODELS: list[dict[str, str]] = [
    {"id": "openai:gpt-4.1", "label": "GPT-4.1", "hint": "быстро, дёшево"},
    {"id": "openai:gpt-5.1", "label": "GPT-5.1", "hint": "размышляет, точнее"},
    {"id": "openai:gpt-4o-mini", "label": "GPT-4o mini", "hint": "самый дешёвый"},
]
_SKILL_CHAT_MODEL_IDS = {m["id"] for m in SKILL_CHAT_MODELS}


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _get_skill_or_404(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID, skill_id: UUID, include_deleted: bool = False
) -> ExpertSkill:
    stmt = select(ExpertSkill).where(
        ExpertSkill.id == skill_id,
        ExpertSkill.agent_id == agent_id,
        ExpertSkill.tenant_id == tenant_id,
    )
    if not include_deleted:
        stmt = stmt.where(ExpertSkill.is_deleted.is_(False))
    skill = (await db.execute(stmt)).scalar_one_or_none()
    if skill is None:
        raise _api_error("not_found", "Навык не найден", status.HTTP_404_NOT_FOUND)
    return skill


async def _distill_from_flow(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID, flow_id: UUID, service_name: str
) -> dict[str, Any]:
    """Разовая дистилляция skill_doc из compiled_text потока (импорт)."""
    stmt = select(ScriptFlow).where(
        ScriptFlow.id == flow_id,
        ScriptFlow.agent_id == agent_id,
        ScriptFlow.tenant_id == tenant_id,
        ScriptFlow.is_deleted.is_(False),
    )
    flow = (await db.execute(stmt)).scalar_one_or_none()
    if flow is None:
        raise _api_error("flow_not_found", "Поток-источник не найден", status.HTTP_404_NOT_FOUND)
    if not (flow.compiled_text or "").strip():
        raise _api_error(
            "not_compiled",
            "Поток-источник не скомпилирован — опубликуйте его перед импортом.",
            status.HTTP_409_CONFLICT,
        )
    openai_api_key = await get_decrypted_api_key(db, tenant_id)
    if not openai_api_key:
        raise _api_error("no_llm_key", "Не настроен ключ OpenAI для тенанта.", status.HTTP_400_BAD_REQUEST)
    try:
        return await distill_skill(flow.compiled_text, service_name or flow.name, openai_api_key=openai_api_key)
    except Exception as exc:  # noqa: BLE001
        logger.exception("skill_import_distill_failed", flow_id=str(flow_id))
        raise _api_error("distill_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/expert-skills/skill-chat/models", response_model=dict)
async def list_skill_chat_models(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    return {"models": SKILL_CHAT_MODELS, "default": get_settings().skill_chat_model}


@router.get("/expert-skills/trash", response_model=list[ExpertSkillRead])
async def list_deleted_expert_skills(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[ExpertSkillRead]:
    """Корзина навыков — удалённые (для восстановления)."""
    await get_agent_or_404(agent_id, db, user)
    stmt = (
        select(ExpertSkill)
        .where(
            ExpertSkill.agent_id == agent_id,
            ExpertSkill.tenant_id == user.tenant_id,
            ExpertSkill.is_deleted.is_(True),
        )
        .order_by(ExpertSkill.deleted_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [ExpertSkillRead.model_validate(r) for r in rows]


@router.get("/expert-skills/style-library", response_model=dict)
async def get_style_library(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Библиотека стиля: все фразы/запреты эксперта из опубликованных навыков
    + какие из них реально попали в стиль-слой (звучат в каждом ответе).

    Read-only витрина для раздела «Эксперт»: карточки собираются из skill_doc
    на лету, отдельного хранилища у v1 нет.
    """
    from app.services.runtime.skill_layer import (
        _iter_skill_phrases,
        render_style_digest,
    )

    await get_agent_or_404(agent_id, db, user)
    settings = get_settings()
    stmt = (
        select(ExpertSkill.name, ExpertSkill.skill_doc)
        .where(
            ExpertSkill.agent_id == agent_id,
            ExpertSkill.tenant_id == user.tenant_id,
            ExpertSkill.status == "published",
            ExpertSkill.is_deleted.is_(False),
            ExpertSkill.skill_doc.isnot(None),
        )
        .order_by(ExpertSkill.updated_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    docs: list[tuple[str, dict[str, Any]]] = []
    for name, skill_doc in rows:
        if isinstance(skill_doc, str):
            try:
                skill_doc = json.loads(skill_doc)
            except (TypeError, ValueError):
                continue
        if isinstance(skill_doc, dict):
            docs.append((str(name or ""), skill_doc))

    digest = render_style_digest(docs) or ""
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for skill_name, skill_doc in docs:
        musts, verbatims, examples, forbidden, _endings = _iter_skill_phrases(skill_doc)
        for kind, items in (
            ("обязательно", musts),
            ("дословно", verbatims),
            ("пример", examples),
        ):
            for trigger, phrase in items:
                key = phrase.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                cards.append({
                    "kind": kind,
                    "trigger": trigger,
                    "text": phrase,
                    "skill_name": skill_name,
                    "in_style_layer": phrase in digest,
                })
        for f in forbidden:
            key = ("forbid:" + f.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            cards.append({
                "kind": "запрет",
                "trigger": "",
                "text": f,
                "skill_name": skill_name,
                "in_style_layer": f in digest,
            })

    counts: dict[str, int] = {}
    for c in cards:
        counts[c["kind"]] = counts.get(c["kind"], 0) + 1

    return {
        "style_layer_enabled": bool(settings.runtime_style_layer_enabled),
        "skills_published": len(docs),
        "digest_chars": len(digest),
        "in_style_layer_count": sum(1 for c in cards if c["in_style_layer"]),
        "counts": counts,
        "cards": cards,
    }


@router.get("/expert-skills", response_model=list[ExpertSkillRead])
async def list_expert_skills(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[ExpertSkillRead]:
    await get_agent_or_404(agent_id, db, user)
    stmt = (
        select(ExpertSkill)
        .where(
            ExpertSkill.agent_id == agent_id,
            ExpertSkill.tenant_id == user.tenant_id,
            ExpertSkill.is_deleted.is_(False),
        )
        .order_by(ExpertSkill.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [ExpertSkillRead.model_validate(r) for r in rows]


@router.post("/expert-skills", response_model=ExpertSkillRead, status_code=status.HTTP_201_CREATED)
async def create_expert_skill(
    agent_id: UUID,
    payload: ExpertSkillCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ExpertSkillRead:
    await get_agent_or_404(agent_id, db, user)
    skill_doc: dict[str, Any] | None = None
    if payload.import_from_flow_id is not None:
        skill_doc = await _distill_from_flow(
            db,
            agent_id=agent_id,
            tenant_id=user.tenant_id,
            flow_id=payload.import_from_flow_id,
            service_name=payload.name,
        )
    skill = ExpertSkill(
        id=uuid4(),
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        name=payload.name,
        service_external_ids=list(payload.service_external_ids or []),
        skill_doc=skill_doc,
        status="draft",
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return ExpertSkillRead.model_validate(skill)


@router.get("/expert-skills/{skill_id}", response_model=ExpertSkillRead)
async def get_expert_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ExpertSkillRead:
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    return ExpertSkillRead.model_validate(skill)


@router.patch("/expert-skills/{skill_id}", response_model=ExpertSkillRead)
async def patch_expert_skill(
    agent_id: UUID,
    skill_id: UUID,
    payload: ExpertSkillUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ExpertSkillRead:
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    if payload.name is not None:
        skill.name = payload.name
    if payload.service_external_ids is not None:
        skill.service_external_ids = list(payload.service_external_ids)
    if payload.status is not None:
        if payload.status not in ("draft", "published"):
            raise _api_error("bad_status", "status ∈ {draft, published}", status.HTTP_422_UNPROCESSABLE_ENTITY)
        skill.status = payload.status
    await db.commit()
    await db.refresh(skill)
    return ExpertSkillRead.model_validate(skill)


@router.post("/expert-skills/{skill_id}/publish", response_model=ExpertSkillRead)
async def publish_expert_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ExpertSkillRead:
    """Опубликовать навык — рантайм (навык-слой + use_expert_skill) начнёт его использовать."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    if not isinstance(skill.skill_doc, dict) or not (skill.skill_doc.get("objections") or skill.skill_doc.get("gaps")):
        raise _api_error(
            "empty_skill",
            "Навык пуст — соберите структуру в чате перед публикацией.",
            status.HTTP_409_CONFLICT,
        )
    skill.status = "published"
    await db.commit()
    await db.refresh(skill)
    return ExpertSkillRead.model_validate(skill)


@router.post("/expert-skills/{skill_id}/unpublish", response_model=ExpertSkillRead)
async def unpublish_expert_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ExpertSkillRead:
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    skill.status = "draft"
    await db.commit()
    await db.refresh(skill)
    return ExpertSkillRead.model_validate(skill)


@router.delete("/expert-skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expert_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    """Мягкое удаление — навык уходит в корзину, восстановим через /restore."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    skill.is_deleted = True
    skill.deleted_at = datetime.now(timezone.utc)
    skill.status = "draft"  # снять с публикации, чтобы рантайм перестал его брать
    await db.commit()


@router.post("/expert-skills/{skill_id}/restore", response_model=ExpertSkillRead)
async def restore_expert_skill(
    agent_id: UUID,
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ExpertSkillRead:
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(
        db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id, include_deleted=True
    )
    skill.is_deleted = False
    skill.deleted_at = None
    await db.commit()
    await db.refresh(skill)
    return ExpertSkillRead.model_validate(skill)


@router.post("/expert-skills/{skill_id}/import-from-flow", response_model=dict)
async def import_skill_from_flow(
    agent_id: UUID,
    skill_id: UUID,
    body: ImportFromFlowBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Перезаписать skill_doc навыка дистилляцией из выбранного потока (разово)."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    skill_doc = await _distill_from_flow(
        db, agent_id=agent_id, tenant_id=user.tenant_id, flow_id=body.flow_id, service_name=skill.name
    )
    skill.skill_doc = skill_doc
    await db.commit()
    await db.refresh(skill)
    return {
        "id": str(skill.id),
        "skill_doc": skill_doc,
        "objections": len(skill_doc.get("objections") or []),
        "gaps": len(skill_doc.get("gaps") or []),
    }


@router.patch("/expert-skills/{skill_id}/skill-doc", response_model=dict)
async def update_expert_skill_doc(
    agent_id: UUID,
    skill_id: UUID,
    payload: SkillDocPatch,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Сохранить ручные правки структуры навыка (skill_doc)."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    normalized = _sanitize_skill_doc(payload.skill_doc or {})
    skill.skill_doc = normalized
    await db.commit()
    await db.refresh(skill)
    return {
        "id": str(skill.id),
        "skill_doc": normalized,
        "objections": len(normalized.get("objections") or []),
        "gaps": len(normalized.get("gaps") or []),
    }


@router.post("/expert-skills/{skill_id}/skill-chat", response_model=dict)
async def skill_chat(
    agent_id: UUID,
    skill_id: UUID,
    body: SkillChatBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Разговорная сборка навыка: эксперт передаёт опыт → skill_doc (не сохраняет)."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    openai_api_key = await get_decrypted_api_key(db, skill.tenant_id)
    if not openai_api_key:
        raise _api_error("no_llm_key", "Не настроен ключ OpenAI для тенанта.", status.HTTP_400_BAD_REQUEST)
    chosen_model = body.model if body.model in _SKILL_CHAT_MODEL_IDS else None
    try:
        result = await converse_skill(
            messages=[m.model_dump() for m in body.messages],
            attachments=[a.model_dump() for a in body.attachments],
            current_skill_doc=body.skill_doc if body.skill_doc is not None else skill.skill_doc,
            service_name=skill.name,
            openai_api_key=openai_api_key,
            model=chosen_model,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("skill_chat_failed", skill_id=str(skill.id))
        raise _api_error("skill_chat_error", str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    additions = result["additions"]
    return {
        "reply": result["reply"],
        "additions": additions,
        "added_objections": len(additions.get("objections") or []),
        "added_gaps": len(additions.get("gaps") or []),
    }


@router.post("/expert-skills/{skill_id}/skill-chat/stream")
async def skill_chat_stream(
    agent_id: UUID,
    skill_id: UUID,
    body: SkillChatBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> EventSourceResponse:
    """Потоковая версия skill-chat: reply приходит по мере генерации (SSE)."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    openai_api_key = await get_decrypted_api_key(db, skill.tenant_id)
    if not openai_api_key:
        raise _api_error("no_llm_key", "Не настроен ключ OpenAI для тенанта.", status.HTTP_400_BAD_REQUEST)
    chosen_model = body.model if body.model in _SKILL_CHAT_MODEL_IDS else None
    current_doc = body.skill_doc if body.skill_doc is not None else skill.skill_doc
    msgs = [m.model_dump() for m in body.messages]
    atts = [a.model_dump() for a in body.attachments]
    skill_name = skill.name

    async def event_generator():
        try:
            async for kind, payload in converse_skill_stream(
                messages=msgs,
                attachments=atts,
                current_skill_doc=current_doc,
                service_name=skill_name,
                openai_api_key=openai_api_key,
                model=chosen_model,
            ):
                if kind == "delta":
                    yield {"event": "delta", "data": json.dumps({"text": payload})}
                elif kind == "done":
                    yield {"event": "done", "data": json.dumps(payload, ensure_ascii=False)}
        except Exception as exc:  # noqa: BLE001
            logger.exception("skill_chat_stream_failed", skill_id=str(skill_id))
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(
        event_generator(),
        ping=15,
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.get("/expert-skills/{skill_id}/review-dialogs", response_model=dict)
async def get_expert_skill_review_dialogs(
    agent_id: UUID,
    skill_id: UUID,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Реальные ходы агента по услугам навыка — основа ревью-инбокса."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    svc_ids = [str(x) for x in (skill.service_external_ids or []) if str(x).strip()]
    lim = max(1, min(int(limit or 30), 100))

    params: dict[str, Any] = {"aid": agent_id, "lim": lim}
    if svc_ids:
        params["svcs"] = svc_ids
        rows = (
            await db.execute(
                text(
                    """
                    WITH skill_sessions AS (
                        SELECT DISTINCT r.session_id
                        FROM tool_call_logs tcl
                        JOIN runs r ON r.id = tcl.run_id
                        WHERE r.agent_id = :aid
                          AND tcl.tool_name = 'resolve_clinic_facts'
                          AND (
                            (tcl.response_payload #>> '{resolved,service_external_id}') = ANY(:svcs)
                            OR EXISTS (
                              SELECT 1
                              FROM jsonb_array_elements(
                                COALESCE(tcl.response_payload->'services', '[]'::jsonb)
                              ) AS svc
                              WHERE (svc->>'external_id') = ANY(:svcs)
                            )
                          )
                    )
                    SELECT r.id, r.session_id, r.input_message, r.output_message,
                           r.tools_called, r.created_at
                    FROM runs r
                    JOIN skill_sessions s ON s.session_id = r.session_id
                    WHERE r.agent_id = :aid AND r.status = 'succeeded'
                    ORDER BY r.created_at DESC
                    LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()
    else:
        rows = (
            await db.execute(
                text(
                    """
                    SELECT r.id, r.session_id, r.input_message, r.output_message,
                           r.tools_called, r.created_at
                    FROM runs r
                    WHERE r.agent_id = :aid AND r.status = 'succeeded'
                    ORDER BY r.created_at DESC
                    LIMIT :lim
                    """
                ),
                params,
            )
        ).fetchall()

    dialogs = [
        {
            "run_id": str(row.id),
            "session_id": row.session_id,
            "input": row.input_message,
            "output": row.output_message,
            "tool_names": [
                c.get("name")
                for c in (row.tools_called or [])
                if isinstance(c, dict) and c.get("name")
            ],
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
    return {"dialogs": dialogs, "has_service_link": bool(svc_ids)}


@router.post("/expert-skills/{skill_id}/review-correction", response_model=dict)
async def add_expert_skill_review_correction(
    agent_id: UUID,
    skill_id: UUID,
    body: ReviewCorrectionBody,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> dict:
    """Правка из ревью → в skill_doc (фраза «как надо» → обработка, иначе → пробел)."""
    await get_agent_or_404(agent_id, db, user)
    skill = await _get_skill_or_404(db, agent_id=agent_id, tenant_id=user.tenant_id, skill_id=skill_id)
    doc = copy.deepcopy(skill.skill_doc) if isinstance(skill.skill_doc, dict) else {}
    doc.setdefault("context", "")
    for key in ("objections", "sequence", "facts_from_tool", "endings", "gaps"):
        doc.setdefault(key, [])

    situation = (body.situation or "").strip()
    if not situation:
        raise _api_error("empty_situation", "Ситуация обязательна.", status.HTTP_422_UNPROCESSABLE_ENTITY)

    phrase = (body.phrase or "").strip()
    if phrase:
        level = body.level if body.level in ("пример", "дословно", "обязательно") else "пример"
        doc["objections"].append(
            {
                "situation": situation,
                "trigger_when": (body.trigger_when or "").strip(),
                "approach": (body.approach or "").strip(),
                "phrases": [{"text": phrase, "level": level}],
                "forbidden": [],
            }
        )
    else:
        doc["gaps"].append({"situation": situation, "trigger_when": (body.trigger_when or "").strip()})

    normalized = _sanitize_skill_doc(doc)
    skill.skill_doc = normalized
    await db.commit()
    await db.refresh(skill)
    return {
        "id": str(skill.id),
        "skill_doc": normalized,
        "objections": len(normalized.get("objections") or []),
        "gaps": len(normalized.get("gaps") or []),
    }
