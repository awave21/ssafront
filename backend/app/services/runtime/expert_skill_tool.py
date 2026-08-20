"""Тул `use_expert_skill` — выбор навыка САМОЙ моделью (как Claude Agent Skills).

В отличие от детерминированного навык-слоя (по услуге), здесь выбирает LLM:
модель видит каталог навыков (название + о чём каждый) в описании тула и, когда
разговор идёт про эту тему, вызывает тул с названием навыка → получает полную
инструкцию эксперта (render_skill_doc: ситуации/фразы/обработки по этапам) и ведёт
диалог по ней. Это progressive disclosure — как у скилов моделей.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai.tools import Tool as PydanticTool, ToolDefinition

from app.services.runtime.skill_layer import render_skill_doc

logger = structlog.get_logger(__name__)


async def list_published_skills(db: AsyncSession, agent_id: UUID) -> list[dict[str, Any]]:
    """Опубликованные навыки агента (с skill_doc) — каталог для выбора моделью."""
    rows = (
        await db.execute(
            text(
                """
                SELECT name, skill_doc
                FROM expert_skills
                WHERE agent_id = :aid
                  AND status = 'published'
                  AND is_deleted = false
                  AND skill_doc IS NOT NULL
                ORDER BY name
                """
            ),
            {"aid": agent_id},
        )
    ).fetchall()
    out: list[dict[str, Any]] = []
    for name, skill_doc in rows:
        if not isinstance(skill_doc, dict):
            continue
        context = str(skill_doc.get("context") or "").strip()
        out.append({"name": str(name or ""), "context": context, "skill_doc": skill_doc})
    return out


def build_expert_skill_tool(*, skills: list[dict[str, Any]]) -> PydanticTool:
    """Тул выбора навыка САМОЙ моделью (агентский путь, как Claude Agent Skills).

    Идиоматично для pydantic-ai 1.x: типизированная функция-инструмент + `prepare`
    для динамического представления тула. Каталог навыков и правило «когда звать»
    зашиты в description — по нему модель решает, вызывать ли навык. Никакого
    per-model толчка в system_prompt: поведение модель-агностично (рантайм-модель
    сменяема). `skills` — предзагруженный каталог (list_published_skills).
    """
    by_name = {s["name"].strip().lower(): s for s in skills}

    catalog_lines = [
        f"- «{s['name']}» — {s['context'][:220] if s['context'] else 'навык по этой теме'}"
        for s in skills
    ]
    catalog = "\n".join(catalog_lines) if catalog_lines else "(навыков нет)"

    description = (
        "Подробные НАВЫКИ ЭКСПЕРТА по темам/услугам клиники — накопленный опыт: как вести "
        "пациента и какими словами (ситуации, фразы, обработки возражений по этапам диалога). "
        "Как только разговор касается одной из тем ниже — ВЫЗОВИ этот инструмент ПЕРВЫМ, ещё "
        "до своего ответа, с названием навыка; получи инструкцию эксперта и веди диалог строго "
        "по ней (голосом эксперта; факты — цены/слоты/врачи — всё равно из других инструментов).\n\n"
        f"Доступные навыки:\n{catalog}"
    )

    async def use_expert_skill(skill: str) -> dict[str, Any]:
        """Загрузить инструкцию навыка эксперта и дальше вести диалог по ней.

        Args:
            skill: Название навыка из каталога в описании (точно или близко по смыслу).
        """
        q = str(skill or "").strip().lower()
        found = by_name.get(q)
        if not found:
            for k, v in by_name.items():
                if q and (q in k or k in q):
                    found = v
                    break
        if not found:
            return {
                "status": "not_found",
                "message": "Навык не найден. Выбери один из доступных.",
                "available": [s["name"] for s in skills],
            }
        instruction = render_skill_doc(found["skill_doc"], service_name=found["name"])
        logger.info("expert_skill_loaded", skill=found["name"])
        return {"status": "ok", "skill": found["name"], "instruction": instruction}

    async def _prepare(ctx: Any, tool_def: ToolDefinition) -> ToolDefinition | None:
        # Динамическое представление тула (pydantic-ai prepare): если опубликованных
        # навыков нет — не показываем тул модели вовсе. Здесь же точка расширения для
        # условного показа (например, прятать, когда тема заведомо не про навык).
        if not by_name:
            return None
        return tool_def

    return PydanticTool(
        function=use_expert_skill,
        takes_ctx=False,
        name="use_expert_skill",
        description=description,
        prepare=_prepare,
    )
