"""Sync SQNS services and specialists to Neo4j with embeddings."""
from __future__ import annotations

from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.db.models.sqns_service import SqnsResource, SqnsService, SqnsServiceResource
from app.services.directory.service import create_embeddings_batch
from app.services.runtime.neo4j_client import get_neo4j_driver

logger = structlog.get_logger(__name__)

_SERVICE_VECTOR_INDEX_NAME = "service_embedding"
_SPECIALIST_VECTOR_INDEX_NAME = "specialist_embedding"
_VECTOR_DIMS = 1536


def _ensure_service_indexes(tx) -> None:
    """Create vector indexes for Service and Specialist nodes if not exist."""
    tx.run(
        f"""
        CREATE VECTOR INDEX {_SERVICE_VECTOR_INDEX_NAME} IF NOT EXISTS
        FOR (n:Service) ON (n.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {_VECTOR_DIMS},
            `vector.similarity_function`: 'cosine'
        }}}}
        """
    )
    tx.run(
        f"""
        CREATE VECTOR INDEX {_SPECIALIST_VECTOR_INDEX_NAME} IF NOT EXISTS
        FOR (n:Specialist) ON (n.embedding)
        OPTIONS {{indexConfig: {{
            `vector.dimensions`: {_VECTOR_DIMS},
            `vector.similarity_function`: 'cosine'
        }}}}
        """
    )


async def sync_sqns_to_neo4j(
    *,
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    openai_api_key: str | None,
) -> None:
    """Sync active SQNS services and specialists to Neo4j with embeddings.

    - Creates/updates :Service nodes from sqns_services (is_enabled=true, stale_since=null)
    - Creates/updates :Specialist nodes from sqns_resources (is_active=true, active=true)
    - Creates :Service -[:PROVIDED_BY]-> :Specialist edges based on service_links
    - Computes embeddings for both node types from text fields
    """
    settings = get_settings()
    if not settings.neo4j_enabled:
        return

    driver = get_neo4j_driver()
    if driver is None:
        logger.warning("sqns_neo4j_sync_skipped_no_driver", agent_id=str(agent_id))
        return

    database = settings.neo4j_database or None
    tenant_id_str = str(tenant_id)
    agent_id_str = str(agent_id)

    # Load active services from DB (with resource links eagerly loaded for edge creation)
    services_stmt = (
        select(SqnsService)
        .where(
            and_(
                SqnsService.agent_id == agent_id,
                SqnsService.is_enabled == True,
                SqnsService.stale_since.is_(None),
            )
        )
        .options(
            selectinload(SqnsService.resource_links).selectinload(SqnsServiceResource.resource)
        )
    )
    services_result = await db.execute(services_stmt)
    services = services_result.scalars().all()

    # Load active specialists from DB
    specialists_stmt = select(SqnsResource).where(
        and_(
            SqnsResource.agent_id == agent_id,
            SqnsResource.is_active == True,
            SqnsResource.active == True,
        )
    )
    specialists_result = await db.execute(specialists_stmt)
    specialists = specialists_result.scalars().all()

    # Очищаем медкоды (A11.01.003, B01.008.004 и т.п.) из названий услуг —
    # пациенту они не нужны, в графе не нужны, в embedding шумят.
    from app.services.runtime.graphrag_tool import _strip_service_code

    service_clean_names: list[str] = [_strip_service_code(s.name) for s in services]

    # Загружаем графовый контекст из Neo4j: для каждой услуги — её специалистов
    # и сценарии где она упоминается; для специалиста — его услуги.
    # Это обогащает embedding смежной семантикой ("ботокс" найдётся через Иванову).
    svc_ctx_by_id: dict[int, dict[str, list[str]]] = {}
    sp_ctx_by_id: dict[int, dict[str, list[str]]] = {}
    if services or specialists:
        try:
            with driver.session(database=database) as ctx_session:
                if services:
                    for row in ctx_session.run(
                        """
                        MATCH (s:Service {tenant_id: $tid, agent_id: $aid})
                        OPTIONAL MATCH (s)-[:PROVIDED_BY]->(sp:Specialist)
                        OPTIONAL MATCH (f:FlowNode {tenant_id: $tid, agent_id: $aid})-[:COVERS_SERVICE]->(s)
                        RETURN s.external_id AS sid,
                               collect(DISTINCT sp.name)[..10] AS specialists,
                               collect(DISTINCT f.flow_name)[..5] AS flow_names,
                               collect(DISTINCT f.title)[..5] AS canvas_titles
                        """,
                        tid=tenant_id_str,
                        aid=agent_id_str,
                    ):
                        svc_ctx_by_id[row["sid"]] = {
                            "specialists": [n for n in (row["specialists"] or []) if n],
                            "flow_names": [n for n in (row["flow_names"] or []) if n],
                            "canvas_titles": [n for n in (row["canvas_titles"] or []) if n],
                        }
                if specialists:
                    for row in ctx_session.run(
                        """
                        MATCH (sp:Specialist {tenant_id: $tid, agent_id: $aid})
                        OPTIONAL MATCH (s:Service)-[:PROVIDED_BY]->(sp)
                        OPTIONAL MATCH (f:FlowNode {tenant_id: $tid, agent_id: $aid})-[:HAS_SPECIALIST]->(sp)
                        RETURN sp.external_id AS sid,
                               collect(DISTINCT s.name)[..10] AS services,
                               collect(DISTINCT f.flow_name)[..5] AS flow_names
                        """,
                        tid=tenant_id_str,
                        aid=agent_id_str,
                    ):
                        sp_ctx_by_id[row["sid"]] = {
                            "services": [n for n in (row["services"] or []) if n],
                            "flow_names": [n for n in (row["flow_names"] or []) if n],
                        }
        except Exception as exc:  # noqa: BLE001
            logger.warning("sqns_neo4j_context_load_failed", error=str(exc))

    def _build_service_text(i: int, s: SqnsService) -> str:
        ctx = svc_ctx_by_id.get(s.external_id, {})
        parts: list[str] = [service_clean_names[i] or s.name]
        if s.category:
            parts.append(f"Категория: {s.category}")
        if s.description:
            parts.append(s.description)
        sp_names = ctx.get("specialists") or []
        if sp_names:
            parts.append(f"Специалисты: {', '.join(sp_names)}")
        flow_names = ctx.get("flow_names") or []
        if flow_names:
            parts.append(f"Тематика в скриптах: {', '.join(flow_names)}")
        return "\n".join(parts).strip()

    def _build_specialist_text(sp: SqnsResource) -> str:
        ctx = sp_ctx_by_id.get(sp.external_id, {})
        parts: list[str] = [sp.name]
        if sp.specialization:
            parts.append(f"Специализация: {sp.specialization}")
        if sp.information:
            parts.append(sp.information)
        sv_names = ctx.get("services") or []
        if sv_names:
            parts.append(f"Услуги: {', '.join(sv_names)}")
        flow_names = ctx.get("flow_names") or []
        if flow_names:
            parts.append(f"Сценарии скриптов: {', '.join(flow_names)}")
        return "\n".join(parts).strip()

    service_texts = [_build_service_text(i, s) for i, s in enumerate(services)]
    specialist_texts = [_build_specialist_text(sp) for sp in specialists]

    service_embeddings: list[list[float] | None] = (
        await create_embeddings_batch(
            service_texts,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.sqns_service",
            charge_source_id=agent_id_str,
            charge_metadata={"agent_id": agent_id_str},
        )
        if services and openai_api_key
        else [None] * len(services)
    )
    specialist_embeddings: list[list[float] | None] = (
        await create_embeddings_batch(
            specialist_texts,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_type="embedding.sqns_specialist",
            charge_source_id=agent_id_str,
            charge_metadata={"agent_id": agent_id_str},
        )
        if specialists and openai_api_key
        else [None] * len(specialists)
    )

    service_rows: list[dict] = [
        {
            "external_id": s.external_id,
            # Чистое название без медкода — для отображения в UI и в LLM-ответах.
            "name": service_clean_names[i] or s.name,
            "category": s.category,
            "description": s.description or "",
            "price": float(s.price) if s.price else None,
            "duration_seconds": s.duration_seconds,
            "embedding": service_embeddings[i] if i < len(service_embeddings) else None,
        }
        for i, s in enumerate(services)
    ]
    specialist_rows: list[dict] = [
        {
            "external_id": sp.external_id,
            "name": sp.name,
            "specialization": sp.specialization or "",
            "information": sp.information or "",
            "embedding": specialist_embeddings[i] if i < len(specialist_embeddings) else None,
        }
        for i, sp in enumerate(specialists)
    ]

    # Collect Service↔Specialist pairs for edges BEFORE entering sync Neo4j transaction.
    # Accessing service.resource_links inside _write would trip async lazy-loading.
    edge_pairs: list[tuple[int, int]] = []
    for service in services:
        for link in service.resource_links:
            if link.resource and link.resource.is_active and link.resource.active:
                edge_pairs.append((service.external_id, link.resource.external_id))

    # Списки активных external_id — для selective delete (без сноса связей).
    active_service_ids = [s.external_id for s in services]
    active_specialist_ids = [sp.external_id for sp in specialists]

    def _write(tx) -> None:
        # Удаляем только устаревшие услуги/специалистов которых больше нет в SQNS.
        # MERGE ниже обновляет существующие — рёбра COVERS_SERVICE/PROVIDED_BY сохраняются.
        tx.run(
            """
            MATCH (n:Service {tenant_id: $tenant_id, agent_id: $agent_id})
            WHERE NOT n.external_id IN $active_ids
            DETACH DELETE n
            """,
            tenant_id=tenant_id_str,
            agent_id=agent_id_str,
            active_ids=active_service_ids,
        )
        tx.run(
            """
            MATCH (n:Specialist {tenant_id: $tenant_id, agent_id: $agent_id})
            WHERE NOT n.external_id IN $active_ids
            DETACH DELETE n
            """,
            tenant_id=tenant_id_str,
            agent_id=agent_id_str,
            active_ids=active_specialist_ids,
        )
        # Также чистим устаревшие PROVIDED_BY рёбра между активными сервисами/специалистами
        # перед тем как пересоздать актуальные. COVERS_SERVICE/HAS_SPECIALIST не трогаем —
        # они принадлежат flow-индексации.
        tx.run(
            """
            MATCH (s:Service {tenant_id: $tenant_id, agent_id: $agent_id})-[r:PROVIDED_BY]->()
            DELETE r
            """,
            tenant_id=tenant_id_str,
            agent_id=agent_id_str,
        )

        # Write services
        for service in service_rows:
            tx.run(
                """
                MERGE (s:Service {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $external_id})
                SET s:Searchable,
                    s.name = $name,
                    s.category = $category,
                    s.description = $description,
                    s.price = $price,
                    s.duration_seconds = $duration_seconds,
                    s.embedding = $embedding
                """,
                tenant_id=tenant_id_str,
                agent_id=agent_id_str,
                **service,
            )

        # Write specialists
        for specialist in specialist_rows:
            tx.run(
                """
                MERGE (sp:Specialist {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $external_id})
                SET sp:Searchable,
                    sp.name = $name,
                    sp.specialization = $specialization,
                    sp.information = $information,
                    sp.embedding = $embedding
                """,
                tenant_id=tenant_id_str,
                agent_id=agent_id_str,
                **specialist,
            )

        # Create PROVIDED_BY edges based on precomputed service-resource pairs
        for svc_ext_id, sp_ext_id in edge_pairs:
            tx.run(
                """
                MATCH (s:Service {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $service_external_id})
                MATCH (sp:Specialist {tenant_id: $tenant_id, agent_id: $agent_id, external_id: $specialist_external_id})
                MERGE (s)-[r:PROVIDED_BY {tenant_id: $tenant_id, agent_id: $agent_id}]->(sp)
                """,
                tenant_id=tenant_id_str,
                agent_id=agent_id_str,
                service_external_id=svc_ext_id,
                specialist_external_id=sp_ext_id,
            )

    try:
        with driver.session(database=database) as session:
            session.execute_write(_write)
        logger.info(
            "sqns_neo4j_sync_ok",
            agent_id=agent_id_str,
            services=len(service_rows),
            specialists=len(specialist_rows),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "sqns_neo4j_sync_failed",
            agent_id=agent_id_str,
            error=str(exc),
        )
