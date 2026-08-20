"""Единый рантайм-тул `resolve_clinic_facts` — подбор услуг/врачей по смыслу запроса.

Заменяет booking-подбор через query_graphrag + ILIKE-матч в sqns_find_booking_options.
Пациент говорит намерением («убрать морщины», «ботокс»), тул через гибридный поиск
(app/services/sqns/hybrid_search.py) находит услуги, подтягивает совместимых врачей
(join sqns_service_resources) и возвращает СТАБИЛЬНЫЕ external_id — их агент передаёт
напрямую в sqns_list_slots / sqns_create_visit (никакого повторного матча по имени).

Регистрируется как optional-категория `clinic_facts` (context_assembler + tool_registry).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai.tools import Tool as PydanticTool

from app.db.models.agent import Agent
from app.services.sqns.hybrid_search import search_resources_hybrid, search_services_hybrid

logger = structlog.get_logger(__name__)

_DESCRIPTION = (
    "Подбор услуг и специалистов клиники по СМЫСЛУ запроса пациента, даже если он не "
    "знает точного названия. Приними свободное намерение ('убрать морщины вокруг глаз', "
    "'подтянуть кожу', 'ботокс', 'чистка лица') — тул гибридным поиском (смысл + название) "
    "найдёт подходящие услуги, их цену и совместимых врачей, и вернёт external_id. "
    "Используй ПЕРВЫМ при запросе на запись или подбор услуги/специалиста, вместо угадывания "
    "названия. external_id услуги и врача из ответа передавай напрямую в sqns_list_slots — "
    "не переспрашивай услугу по имени. "
    "ВАЖНО: у каждого врача в doctors[].information — его правила записи (тип приёма, "
    "приоритеты по услугам, быстрая запись, обязательные уточнения, как называть врача). "
    "Обязательно читай и применяй эти правила при подборе врача и оформлении записи."
)


def _doctor_payload(r: Any, *, override: int | None = None) -> dict[str, Any]:
    """Врач для вывода агенту. `information` хранит правила записи врача (тип приёма,
    приоритеты, быстрая запись, уточнения) — эксперт пишет их в свободной форме,
    отдаём агенту, чтобы он их применял при подборе/записи."""
    payload: dict[str, Any] = {
        "external_id": int(r.external_id),
        "name": r.name,
        "specialization": r.specialization,
    }
    if override is not None:
        payload["duration_seconds_override"] = override
    info = (getattr(r, "information", None) or "").strip()
    if info:
        payload["information"] = info[:1500]
    return payload


async def _eligible_doctors(db: AsyncSession, agent_id: UUID, service_external_id: int) -> list[dict[str, Any]]:
    """Врачи, которые выполняют услугу (join sqns_service_resources) + per-doctor длительность."""
    rows = (await db.execute(text(
        """
        SELECT r.external_id, r.name, r.specialization, r.information,
               sr.duration_seconds AS override_duration
        FROM sqns_resources r
        JOIN sqns_service_resources sr ON sr.resource_id = r.id
        JOIN sqns_services s ON s.id = sr.service_id
        WHERE s.agent_id = :aid AND s.external_id = :svc
          AND r.is_active = true AND r.active = true
        ORDER BY r.name
        """
    ), {"aid": agent_id, "svc": service_external_id})).fetchall()
    return [_doctor_payload(r, override=r.override_duration) for r in rows]


async def _active_doctors_fallback(db: AsyncSession, agent_id: UUID, limit: int = 12) -> list[dict[str, Any]]:
    """Активные специалисты клиники — фолбэк, когда у услуги нет связок в sqns_service_resources.

    Связки заполняются из booking-данных (не из каталога), поэтому у ~69% услуг врачей нет.
    Отдаём активных врачей с пометкой: SQNS валидирует совместимость на sqns_list_slots.
    """
    rows = (await db.execute(text(
        """
        SELECT external_id, name, specialization, information
        FROM sqns_resources
        WHERE agent_id = :aid AND is_active = true AND active = true
        ORDER BY name
        LIMIT :lim
        """
    ), {"aid": agent_id, "lim": limit})).fetchall()
    return [_doctor_payload(r) for r in rows]


def build_resolve_clinic_facts_tool(
    *,
    db: AsyncSession,
    agent: Agent,
    tenant_id: UUID,
    openai_api_key: str | None,
) -> PydanticTool:
    agent_id = agent.id

    async def _resolve(intent: str, want: str = "services", limit: int = 5) -> dict[str, Any]:
        q = str(intent or "").strip()
        if not q:
            return {"status": "no_query", "message": "Пустой запрос — уточни, что нужно пациенту."}
        lim = max(1, min(int(limit or 5), 8))

        if want == "doctors":
            doctors = await search_resources_hybrid(
                db, agent_id=agent_id, query=q, openai_api_key=openai_api_key,
                tenant_id=tenant_id, limit=lim,
            )
            return {
                "status": "ok" if doctors else "no_match",
                "want": "doctors",
                "doctors": doctors,
                "needs_clarification": len(doctors) > 1,
            }

        services = await search_services_hybrid(
            db, agent_id=agent_id, query=q, openai_api_key=openai_api_key,
            tenant_id=tenant_id, limit=lim,
        )
        if not services:
            return {
                "status": "no_match",
                "want": "services",
                "services": [],
                "message": "По смыслу запроса услуга не найдена. Уточни у пациента или предложи sqns_list_categories.",
            }

        # Подтянуть совместимых врачей для топ-услуг (ограничим 3, чтобы не раздувать вывод).
        enriched: list[dict[str, Any]] = []
        for svc in services:
            ext = svc.get("external_id")
            doctors = await _eligible_doctors(db, agent_id, int(ext)) if isinstance(ext, int) else []
            doctors_source = "linked"
            if not doctors:
                # У услуги нет связок врач↔услуга (частый случай) — предлагаем активных
                # врачей; итоговую совместимость проверит SQNS на sqns_list_slots.
                doctors = await _active_doctors_fallback(db, agent_id)
                doctors_source = "fallback_all_active"
            enriched.append({**svc, "doctors": doctors, "doctors_source": doctors_source})

        needs_clarification = len(services) > 1
        resolved = None
        if not needs_clarification:
            top = enriched[0]
            resolved = {
                "service_external_id": top.get("external_id"),
                "doctor_external_ids": [d["external_id"] for d in top.get("doctors", [])],
            }

        return {
            "status": "ok",
            "want": "services",
            "services": enriched,
            "needs_clarification": needs_clarification,
            "resolved": resolved,
            "hint": (
                "Услуга однозначна. Для записи вызови sqns_list_slots с resource_id из doctors[].external_id "
                "и service_ids=[external_id услуги], date=YYYY-MM-DD."
                if resolved else
                "Несколько подходящих услуг — уточни у пациента одну из services[] (по названию), затем бери её external_id."
            ),
        }

    _resolve.__name__ = "resolve_clinic_facts"

    return PydanticTool.from_schema(
        function=_resolve,
        name="resolve_clinic_facts",
        description=_DESCRIPTION,
        json_schema={
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Свободное описание того, что хочет пациент (намерение, симптом, зона, народное название услуги).",
                },
                "want": {
                    "type": "string",
                    "enum": ["services", "doctors"],
                    "default": "services",
                    "description": "services — подобрать услугу (по умолчанию); doctors — искать специалиста.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 8, "default": 5},
            },
            "required": ["intent"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )
