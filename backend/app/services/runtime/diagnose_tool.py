"""Runtime tool `diagnose_client_motive`.

Задача: дать LLM-агенту быстрый способ *диагностировать* текущее сообщение
клиента прежде чем отвечать. В отличие от `search_script_flows`, этот тул
не делает retrieval — он просит LLM структурно выбрать:

- `primary_motive_id`  — id из `agent_kg_entities` (type=motive). Это
  заставляет модель опираться на СУЩНОСТИ, которые завёл эксперт, а не
  выдумывать «драйверы». Если подходящего мотива нет — вернуть `null`.
- `raised_objection_ids` — список id возражений, которые клиент поднял.
- `closed_objection_ids` — список id возражений, которые клиент закрыл
  (принял ответ / согласился).
- `emotional_state` — neutral | anxious | skeptical | angry | excited.
- `funnel_stage` — discovery | consideration | objection | closing | post_sale.
- `needs_clarification` — если мотив/стадия неясны и надо задать
  уточняющий вопрос, а не лезть в тактики.

Side-effect тула: всё это **пишется в `session_script_contexts`** через
`upsert_motive_state`, чтобы последующий вызов `search_script_flows`
видел state и делал rerank, а snapshot в системном промпте обновлялся.

Сам тул НЕ делает отдельного LLM-запроса — мы полагаемся на call-LLM
агента: это её же mini-thinking-step, который она обязана сделать перед
ответом. Это дешевле и убирает второй круг латентности.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from pydantic_ai.tools import Tool as PydanticTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_kg_entity import AgentKgEntity
from app.services.runtime.expertise_policy import (
    build_diagnose_prompt_bridge,
    build_diagnose_tool_description,
)
from app.services.runtime.motive_state import (
    EMOTIONAL_BUFFER_STATES,
    FUNNEL_STAGES,
    upsert_motive_state,
)

logger = structlog.get_logger(__name__)


DEFAULT_TOOL_DESCRIPTION = build_diagnose_tool_description()


DIAGNOSE_PROMPT_BRIDGE = build_diagnose_prompt_bridge(
    emotional_buffer_states=sorted(EMOTIONAL_BUFFER_STATES),
)


async def _load_motive_catalog(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID
) -> dict[str, list[dict[str, Any]]]:
    """Грузит компактный каталог Motive/Objection/Constraint для промпта тула.

    Мы не подсовываем их в тул напрямую, но описание тула заполняется этим
    каталогом, чтобы LLM знала список допустимых id.
    """
    stmt = select(AgentKgEntity).where(
        AgentKgEntity.agent_id == agent_id,
        AgentKgEntity.tenant_id == tenant_id,
        AgentKgEntity.entity_type.in_(("motive", "objection", "constraint")),
    )
    rows = (await db.execute(stmt)).scalars().all()
    catalog: dict[str, list[dict[str, Any]]] = {"motive": [], "objection": [], "constraint": []}
    for r in rows:
        catalog[r.entity_type].append(
            {
                "id": str(r.id),
                "name": r.name,
                "description": r.description or "",
            }
        )
    return catalog


_MAX_MOTIVES_IN_DESCRIPTION = 15
_MAX_OBJECTIONS_IN_DESCRIPTION = 20
_MAX_CONSTRAINTS_IN_DESCRIPTION = 10
_DESC_CUTOFF = 70  # символов для description сущности


def _build_description(catalog: dict[str, list[dict[str, Any]]]) -> str:
    """Вклеиваем список доступных мотивов/возражений в описание тула — так
    LLM выбирает id из списка, а не выдумывает.

    Лимиты на число сущностей защищают от раздутия description при большой KG.
    Наиболее важные сущности (первые в списке — по алфавиту из БД) включаются
    приоритетно; если всего сущностей больше лимита — добавляется счётчик.
    """

    def _fmt(items: list[dict[str, Any]], limit: int) -> str:
        if not items:
            return "  (библиотека пуста — добавьте сущности в разделе KG)"
        shown = items[:limit]
        lines = [
            f"  • {i['id']} — {i['name']}"
            + (f": {i['description'][:_DESC_CUTOFF]}" if i["description"] else "")
            for i in shown
        ]
        if len(items) > limit:
            lines.append(f"  … и ещё {len(items) - limit} (показаны самые релевантные)")
        return "\n".join(lines)

    motives_block = _fmt(catalog["motive"], _MAX_MOTIVES_IN_DESCRIPTION)
    objections_block = _fmt(catalog["objection"], _MAX_OBJECTIONS_IN_DESCRIPTION)
    constraints_block = _fmt(catalog["constraint"], _MAX_CONSTRAINTS_IN_DESCRIPTION)

    parts = [DEFAULT_TOOL_DESCRIPTION]
    parts.append(f"Мотивы (primary_motive_id — выбирай отсюда):\n{motives_block}")
    parts.append(f"Возражения (raised/closed_objection_ids):\n{objections_block}")
    if catalog["constraint"]:
        parts.append(f"Ограничения (для справки):\n{constraints_block}")
    return "\n\n".join(parts)


async def build_diagnose_client_motive_tool(
    *,
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    session_id: UUID | None,
) -> PydanticTool | None:
    """Строит тул или возвращает None, если сессия не известна или каталог
    мотивов пуст (тогда тул бесполезен).
    """
    if session_id is None:
        return None

    catalog = await _load_motive_catalog(db, agent_id=agent_id, tenant_id=tenant_id)
    if not catalog["motive"] and not catalog["objection"]:
        return None

    description = _build_description(catalog)

    # Внутри замыкания храним ссылки для side-effect upsert-а.
    _agent_id = agent_id
    _tenant_id = tenant_id
    _session_id = session_id

    async def _diagnose_client_motive(
        primary_motive_id: str | None = None,
        raised_objection_ids: list[str] | None = None,
        closed_objection_ids: list[str] | None = None,
        emotional_state: str = "neutral",
        funnel_stage: str = "discovery",
        needs_clarification: bool = False,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Diagnoses the latest client message.

        Args:
            primary_motive_id: ID of the dominant motive from the expert
                library, or null if unclear.
            raised_objection_ids: IDs of objections the client just raised.
            closed_objection_ids: IDs of objections the client just accepted.
            emotional_state: One of neutral|anxious|skeptical|angry|excited.
            funnel_stage: One of discovery|consideration|objection|closing|post_sale.
            needs_clarification: True if you need to ask a clarifying
                question instead of going to a tactic.
            confidence: Self-estimate 0..1 of how sure you are in this
                diagnosis.
        """
        es = (emotional_state or "neutral").strip().lower()
        if es not in {"neutral", "anxious", "skeptical", "angry", "excited"}:
            es = "neutral"
        fs = (funnel_stage or "discovery").strip().lower()
        if fs not in FUNNEL_STAGES:
            fs = "discovery"

        # Валидация id — отбрасываем всё, чего нет в каталоге эксперта.
        allowed_motives = {x["id"] for x in catalog["motive"]}
        allowed_objections = {x["id"] for x in catalog["objection"]}

        pm = primary_motive_id if primary_motive_id in allowed_motives else None
        raised = [x for x in (raised_objection_ids or []) if x in allowed_objections]
        closed = [x for x in (closed_objection_ids or []) if x in allowed_objections]

        # before = текущий state, чтобы тул честно отдал LLM флаг
        # `emotional_pause_used_before` — это важно для бриджа.
        from app.services.runtime.motive_state import load_motive_state  # local

        prev = await load_motive_state(
            db, session_id=_session_id, agent_id=_agent_id, tenant_id=_tenant_id
        )
        pause_before = prev.emotional_pause_used

        new_pause_used = pause_before
        # Если клиент в эмоциональном состоянии и это первая такая реплика —
        # помечаем флаг, чтобы на следующем ходу уже не делать «эмо-паузу».
        if es in EMOTIONAL_BUFFER_STATES and not pause_before:
            new_pause_used = True

        state = await upsert_motive_state(
            db,
            session_id=_session_id,
            agent_id=_agent_id,
            tenant_id=_tenant_id,
            detected_motive_ids=[pm] if pm else None,
            raised_objection_ids=raised or None,
            closed_objection_ids=closed or None,
            emotional_state=es,
            funnel_stage=fs,
            emotional_pause_used=new_pause_used,
            last_diagnosis={
                "primary_motive_id": pm,
                "raised": raised,
                "closed": closed,
                "emotional_state": es,
                "funnel_stage": fs,
                "needs_clarification": bool(needs_clarification),
                "confidence": max(0.0, min(1.0, float(confidence))),
            },
        )
        # Commit сразу — иначе следующий tool-call (в той же реплике) не
        # увидит запись. В run_service у нас один session на реплику, так
        # что это безопасно.
        await db.commit()

        return {
            "primary_motive_id": pm,
            "raised_objection_ids": raised,
            "closed_objection_ids": closed,
            "emotional_state": es,
            "funnel_stage": fs,
            "needs_clarification": bool(needs_clarification),
            "confidence": max(0.0, min(1.0, float(confidence))),
            "emotional_pause_used_before": pause_before,
            "emotional_pause_used_now": state.emotional_pause_used,
            "state_summary": {
                "detected_motive_ids": state.detected_motive_ids,
                "open_objection_ids": [
                    x for x in state.raised_objection_ids
                    if x not in state.closed_objection_ids
                ],
                "asked_followup_count": len(state.asked_followup_questions),
            },
        }

    _diagnose_client_motive.__name__ = "diagnose_client_motive"

    return PydanticTool.from_schema(
        function=_diagnose_client_motive,
        name="diagnose_client_motive",
        description=description,
        json_schema={
            "type": "object",
            "properties": {
                "primary_motive_id": {
                    "type": "string",
                    "description": "ID мотива из списка (см. description) или null, если неясно.",
                },
                "raised_objection_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ID возражений, которые клиент ТОЛЬКО ЧТО поднял.",
                },
                "closed_objection_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "ID возражений, которые клиент ТОЛЬКО ЧТО принял/закрыл.",
                },
                "emotional_state": {
                    "type": "string",
                    "enum": ["neutral", "anxious", "skeptical", "angry", "excited"],
                },
                "funnel_stage": {
                    "type": "string",
                    "enum": list(FUNNEL_STAGES),
                },
                "needs_clarification": {
                    "type": "boolean",
                    "description": "True, если нужно уточнение, а не тактика.",
                },
                "confidence": {
                    "type": "number",
                    "description": "0..1 — уверенность в диагнозе.",
                },
            },
            "required": ["emotional_state", "funnel_stage"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )
