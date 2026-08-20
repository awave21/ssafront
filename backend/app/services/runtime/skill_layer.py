"""Навык-слой рантайма: «навык = продолжение эксперта».

Идея: вместо пофрагментной RAG-выборки тактик на каждое сообщение —
подгружать целиком дистиллированный навык (skill_doc) той услуги, что уже
определена в диалоге (по последнему resolve_clinic_facts). Навык формирует
поведение голосом эксперта (дословные фразы, обработки, концовки), но НЕ
подменяет факты — цены/слоты/названия остаются за инструментами.

Врезается в run_service.execute_agent_run как добавка к system_prompt_override,
за флагом settings.runtime_skill_layer_enabled.

Границы (жёстко):
- факты (цены, слоты, названия услуг) — только из resolve_clinic_facts/SQNS;
- фразы уровня «обязательно» подаются как жёсткая инструкция в блоке навыка;
- если для ситуации у эксперта нет фраз (gap) — вести своими словами, не
  выдумывать «фирменных» формулировок.

TODO(follow-up): пост-проверка вывода на дословность «обязательных» фраз
(зеркалить механику _extract_forced_reaction_output), сейчас — prompt-level.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# сколько последних resolve_clinic_facts просматривать в поисках активной услуги
_LOOKBACK = 8

# порядок и названия этапов диалога (для «линии жизни» разговора в промпте)
_STAGE_ORDER = (
    "приветствие", "уточнение", "презентация", "цена", "возражения", "запись", "завершение", "другое",
)
_STAGE_LABELS = {
    "приветствие": "Приветствие",
    "уточнение": "Уточнение потребности",
    "презентация": "Презентация",
    "цена": "Цена",
    "возражения": "Возражения и сомнения",
    "запись": "Запись",
    "завершение": "Завершение",
    "другое": "Другое",
}


async def find_active_service_ids(
    db: AsyncSession, *, agent_id: UUID, session_id: str
) -> list[str]:
    """Кандидаты активных услуг сессии по последним resolve_clinic_facts.

    Приоритет — однозначно определённая услуга (`resolved.service_external_id`).
    Если её нет (частый случай: несколько услуг, нужно уточнение) — берём
    `services[].external_id` самого свежего вызова. Возвращаем строки — так связь
    сравнивается с script_flows.service_external_ids (массив строк).
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT tcl.response_payload
                FROM tool_call_logs tcl
                JOIN runs r ON r.id = tcl.run_id
                WHERE r.agent_id = :aid
                  AND r.session_id = :sid
                  AND tcl.tool_name = 'resolve_clinic_facts'
                ORDER BY tcl.invoked_at DESC
                LIMIT :lim
                """
            ),
            {"aid": agent_id, "sid": session_id, "lim": _LOOKBACK},
        )
    ).fetchall()

    # 1) однозначно определённая услуга — самый надёжный сигнал
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        resolved = payload.get("resolved")
        if isinstance(resolved, dict):
            svc = resolved.get("service_external_id")
            if svc is not None and str(svc).strip():
                return [str(svc)]

    # 2) fallback: услуги-кандидаты из самого свежего вызова
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        services = payload.get("services")
        if isinstance(services, list) and services:
            ids = [
                str(s.get("external_id"))
                for s in services
                if isinstance(s, dict) and s.get("external_id") is not None
            ]
            ids = [i for i in ids if i.strip()]
            if ids:
                return ids
    return []


async def load_skill_docs_for_services(
    db: AsyncSession, *, agent_id: UUID, service_external_ids: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Опубликованные навыки, пересекающиеся с любой из услуг-кандидатов.

    Читаем из expert_skills (навыки отделены от потоков): status=published,
    не удалён. Возвращает [(skill_name, skill_doc), ...] без дублей.
    """
    if not service_external_ids:
        return []
    rows = (
        await db.execute(
            text(
                """
                SELECT name, skill_doc, updated_at
                FROM expert_skills es
                WHERE es.agent_id = :aid
                  AND es.status = 'published'
                  AND es.is_deleted = false
                  AND es.skill_doc IS NOT NULL
                  AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(es.service_external_ids) AS e
                    WHERE e = ANY(:svcs)
                  )
                ORDER BY updated_at DESC
                """
            ),
            {"aid": agent_id, "svcs": [str(s) for s in service_external_ids]},
        )
    ).fetchall()
    out: list[tuple[str, dict[str, Any]]] = []
    for name, skill_doc, _updated in rows:
        if isinstance(skill_doc, dict):
            out.append((str(name or ""), skill_doc))
    return out


def render_skill_doc(skill_doc: dict[str, Any], *, service_name: str) -> str:
    """Собрать блок навыка для system_prompt — связная инструкция голосом эксперта."""
    lines: list[str] = []
    lines.append(f"## НАВЫК ЭКСПЕРТА: {service_name}".rstrip())
    lines.append(
        "Ниже — накопленный опыт эксперта по этой услуге: как вести пациента и "
        "какими словами. Это ТВОЁ продолжение эксперта — держись его подхода и его "
        "формулировок. Факты (цены, слоты, названия) всё равно бери только из "
        "инструментов, не из этого блока."
    )

    context = str(skill_doc.get("context") or "").strip()
    if context:
        lines.append("\n**Контекст навыка:** " + context)

    def _render_objection(o: dict[str, Any]) -> None:
        situation = str(o.get("situation") or "").strip()
        trigger = str(o.get("trigger_when") or "").strip()
        approach = str(o.get("approach") or "").strip()
        head = f"\n— Если клиент: {trigger}" if trigger else (f"\n— Ситуация: {situation}" if situation else "\n—")
        lines.append(head)
        if situation and trigger:
            lines.append(f"  ({situation})")
        if approach:
            lines.append(f"  Подход: {approach}")
        must: list[str] = []
        example: list[str] = []
        for p in o.get("phrases") or []:
            if not isinstance(p, dict):
                continue
            t = str(p.get("text") or "").strip()
            if not t:
                continue
            if str(p.get("level")) == "обязательно":
                must.append(t)
            else:
                example.append(t)
        if example:
            lines.append("  Фразы эксперта (образцы интонации, можно адаптировать):")
            lines.extend(f"    · {t}" for t in example)
        if must:
            lines.append("  Обязательные формулировки (используй практически дословно):")
            lines.extend(f"    ‼ {t}" for t in must)
        forbidden = [str(f).strip() for f in (o.get("forbidden") or []) if str(f).strip()]
        if forbidden:
            lines.append("  Избегай: " + "; ".join(forbidden))

    objections = [o for o in (skill_doc.get("objections") or []) if isinstance(o, dict)]
    if objections:
        lines.append(
            "\n**Как вести диалог по этапам (сверху вниз — ход разговора), голосом эксперта:**"
        )
        by_stage: dict[str, list[dict[str, Any]]] = {}
        for o in objections:
            st = str(o.get("stage") or "другое")
            if st not in _STAGE_ORDER:
                st = "другое"
            by_stage.setdefault(st, []).append(o)
        for stage in _STAGE_ORDER:
            stage_objs = by_stage.get(stage) or []
            if not stage_objs:
                continue
            lines.append(f"\n### Этап: {_STAGE_LABELS[stage]}")
            for o in stage_objs:
                _render_objection(o)

    facts = [str(f).strip() for f in (skill_doc.get("facts_from_tool") or []) if str(f).strip()]
    if facts:
        lines.append(
            "\n**Эти факты бери из инструментов, не из головы:** " + "; ".join(facts)
        )

    endings = [str(e).strip() for e in (skill_doc.get("endings") or []) if str(e).strip()]
    if endings:
        lines.append("\n**Варианты завершений/переходов к шагу:**")
        lines.extend(f"  · {e}" for e in endings)

    gaps = skill_doc.get("gaps") or []
    if gaps:
        lines.append(
            "\n**Пробелы (готовых фраз эксперта нет — веди своими словами, "
            "не выдумывай «фирменных» реплик):**"
        )
        for g in gaps:
            if not isinstance(g, dict):
                continue
            s = str(g.get("situation") or "").strip()
            if s:
                lines.append(f"  · {s}")

    return "\n".join(lines).strip()


async def build_skill_layer_prompt(
    db: AsyncSession, *, agent_id: UUID, session_id: str
) -> str | None:
    """Собрать добавку навык-слоя для system_prompt_override, либо None.

    None — когда услуга ещё не определена или у её потока нет skill_doc.
    """
    service_ids = await find_active_service_ids(
        db, agent_id=agent_id, session_id=session_id
    )
    if not service_ids:
        return None
    docs = await load_skill_docs_for_services(
        db, agent_id=agent_id, service_external_ids=service_ids
    )
    if not docs:
        return None
    blocks = [render_skill_doc(sd, service_name=name) for name, sd in docs if sd]
    blocks = [b for b in blocks if b]
    if not blocks:
        return None
    logger.info(
        "skill_layer_injected",
        agent_id=str(agent_id),
        session_id=session_id,
        service_external_ids=service_ids,
        skills=len(blocks),
    )
    return "\n\n" + "\n\n".join(blocks)
