from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Any, Literal
from uuid import UUID

from pydantic_ai.tools import Tool as PydanticTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.db.models.sqns_service import SqnsEmployee, SqnsResource, SqnsService, SqnsServiceCategory
from app.services.runtime.expertise_policy import build_graphrag_tool_description

import structlog

logger = structlog.get_logger(__name__)

_GRAPHRAG_CLI_METHODS = {"basic", "local", "global", "drift"}

DEFAULT_TOOL_DESCRIPTION = build_graphrag_tool_description()

_TOKEN_RE = re.compile(r"[^0-9a-zа-я]+", re.IGNORECASE)
_ENTITY_SERVICE = "sqns_service"
_ENTITY_SPECIALIST = "sqns_specialist"
_ENTITY_EMPLOYEE = "sqns_employee"
_ENTITY_CATEGORY = "sqns_service_category"


@dataclass
class DomainCandidate:
    name: str
    score: float
    entity_type: str
    graph_node_id: str
    external_id: str | None = None
    additional_info: str | None = None
    information: str | None = None


def _normalize_lookup_text(raw: str | None) -> str:
    text = str(raw or "").strip().lower().replace("ё", "е")
    text = _TOKEN_RE.sub(" ", text)
    return " ".join(text.split())


_SERVICE_CODE_RE = re.compile(r"^\s*[А-ЯA-ZА-Яа-я]\d+[\d.]*\s+")


def _strip_service_code(name: str) -> str:
    """Убирает медицинские классификационные коды из названий услуг (А11.01.12 → '')."""
    return _SERVICE_CODE_RE.sub("", name).strip()


def _prefix_matches(token: str, candidates: list[str]) -> bool:
    """Сравнение слов по общему корню — для обработки падежных форм русского языка.

    Слова считаются совпадающими, если общий префикс >= 4 символов и >= len(короткого) - 2.
    Это покрывает типичные окончания (1-2 символа) в любом домене без хардкода слов.
    """
    if len(token) < 4:
        return False
    for ct in candidates:
        if len(ct) < 4:
            continue
        pfx = 0
        for a, b in zip(token, ct):
            if a == b:
                pfx += 1
            else:
                break
        if pfx >= 4 and pfx >= min(len(token), len(ct)) - 2:
            return True
    return False


def _token_overlap_score(query_norm: str, candidate_norm: str) -> float:
    q_tokens = [t for t in query_norm.split() if t]
    c_tokens_list = [t for t in candidate_norm.split() if t]
    c_tokens_set = set(c_tokens_list)
    if not q_tokens or not c_tokens_list:
        return 0.0
    overlap = sum(
        1 for token in q_tokens
        if token in c_tokens_set or _prefix_matches(token, c_tokens_list)
    )
    return overlap / float(len(q_tokens))


def _score_candidate(query_norm: str, candidate: str) -> float:
    candidate_norm = _normalize_lookup_text(candidate)
    if not query_norm or not candidate_norm:
        return 0.0
    if query_norm == candidate_norm:
        return 1.0
    if len(candidate_norm) >= 4 and candidate_norm in query_norm:
        return 0.95
    if len(query_norm) >= 4 and query_norm in candidate_norm:
        return 0.91
    overlap = _token_overlap_score(query_norm, candidate_norm)
    ratio = SequenceMatcher(None, query_norm, candidate_norm).ratio()
    score = 0.0
    if overlap >= 1.0 and len(query_norm.split()) >= 2:
        score = max(score, 0.88)
    if overlap >= 0.5:
        score = max(score, overlap * 0.84)
    if ratio >= 0.76:
        score = max(score, ratio * 0.82)
    return score


def _score_blob(query_norm: str, *parts: str | None) -> float:
    best = 0.0
    for part in parts:
        if not isinstance(part, str) or not part.strip():
            continue
        best = max(best, _score_candidate(query_norm, part))
        norm = _normalize_lookup_text(part)
        if norm:
            best = max(best, _token_overlap_score(query_norm, norm) * 0.72)
    return best


def _snip(text: str | None, *, limit: int = 240) -> str | None:
    if not isinstance(text, str):
        return None
    s = " ".join(text.strip().split())
    if not s:
        return None
    if len(s) <= limit:
        return s
    return s[:limit].rstrip() + "..."


def _dedupe_candidates(items: list[DomainCandidate]) -> list[DomainCandidate]:
    seen: set[str] = set()
    out: list[DomainCandidate] = []
    for item in items:
        key = item.graph_node_id or item.name
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _candidates_to_payload(items: list[DomainCandidate]) -> list[dict[str, Any]]:
    result = []
    for item in items:
        d: dict[str, Any] = {
            "name": item.name,
            "score": round(float(item.score or 0.0), 4),
            "entity_type": item.entity_type,
            "graph_node_id": item.graph_node_id,
            "external_id": item.external_id,
            "additional_info": item.additional_info,
        }
        if item.information is not None:
            d["information"] = item.information
        result.append(d)
    return result


def _build_clarify_question(*, services: list[DomainCandidate], specialists: list[DomainCandidate]) -> str | None:
    if services:
        if len(services) == 1:
            return None
        top = "; ".join(item.name for item in services[:3])
        return f"Подскажите, какой вариант вам нужен: {top}?"
    if specialists:
        top = "; ".join(item.name for item in specialists[:3])
        return f"К какому специалисту хотите записаться: {top}? И какую услугу планируете?"
    return "Подскажите, пожалуйста, на какую услугу вы хотите записаться?"


def _looks_like_booking_intent(query_norm: str) -> bool:
    if not query_norm:
        return False
    markers = (
        "запис",
        "прием",
        "прием к",
        "на процед",
        "хочу к",
        "подобрать услуг",
        "подобрать специалист",
    )
    return any(marker in query_norm for marker in markers)


def _query_tokens(query_norm: str) -> list[str]:
    return [token for token in query_norm.split() if token][:8]


def _search_preview_matches(
    *,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
    query_norm: str,
    max_candidates: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    ws = agent_graphrag_workspace(settings, tenant_id=tenant_id, agent=agent)
    if ws is None or not ws.is_dir():
        return [], [], "no_workspace"

    payload = load_graphrag_preview_from_workspace(ws)
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    if not nodes:
        preview_source = str(payload.get("preview_source") or "workspace_empty")
        return [], [], preview_source

    scored: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        label = str(node.get("label") or "").strip()
        node_type = str(node.get("type") or "entity").strip() or "entity"
        description = str(node.get("description") or "").strip()
        score = _score_blob(query_norm, label, description, node_type)
        if score <= 0.0:
            continue
        scored.append(
            {
                "name": label or str(node.get("id") or ""),
                "score": round(score, 4),
                "entity_type": node_type,
                "graph_node_id": str(node.get("id") or label),
                "excerpt": _snip(description, limit=260),
            }
        )

    scored.sort(key=lambda item: (float(item.get("score") or 0.0), len(str(item.get("name") or ""))), reverse=True)
    matches = scored[:max_candidates]
    snippets = [
        {
            "title": item.get("name"),
            "excerpt": item.get("excerpt"),
            "graph_node_id": item.get("graph_node_id"),
        }
        for item in matches
        if item.get("excerpt")
    ]
    preview_source = str(payload.get("preview_source") or "workspace_parquet")
    return matches, snippets[:max_candidates], preview_source


async def _search_domain_candidates(
    db: AsyncSession,
    *,
    agent_id: UUID,
    query_norm: str,
    max_candidates: int,
) -> tuple[list[DomainCandidate], list[DomainCandidate], list[DomainCandidate]]:
    service_rows = (
        await db.execute(
            select(SqnsService).where(
                SqnsService.agent_id == agent_id,
                SqnsService.is_enabled.is_(True),
                SqnsService.stale_since.is_(None),
            )
        )
    ).scalars().all()
    category_rows = (
        await db.execute(
            select(SqnsServiceCategory).where(
                SqnsServiceCategory.agent_id == agent_id,
                SqnsServiceCategory.is_enabled.is_(True),
                SqnsServiceCategory.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    specialist_rows = (
        await db.execute(
            select(SqnsResource).where(
                SqnsResource.agent_id == agent_id,
                SqnsResource.active.is_(True),
                SqnsResource.is_active.is_(True),
            )
        )
    ).scalars().all()
    employee_rows = (
        await db.execute(
            select(SqnsEmployee).where(
                SqnsEmployee.agent_id == agent_id,
                SqnsEmployee.is_fired.is_(False),
                SqnsEmployee.is_deleted.is_(False),
            )
        )
    ).scalars().all()

    services: list[DomainCandidate] = []
    for row in service_rows:
        score = _score_blob(query_norm, row.name, row.category, row.description)
        if score <= 0.0:
            continue
        services.append(
            DomainCandidate(
                name=_strip_service_code(row.name),
                score=score,
                entity_type=_ENTITY_SERVICE,
                graph_node_id=f"sqns_service:{row.external_id}",
                external_id=str(row.external_id),
                additional_info=(row.category or None),
            )
        )

    categories: list[DomainCandidate] = []
    for row in category_rows:
        score = _score_blob(query_norm, row.name)
        if score <= 0.0:
            continue
        categories.append(
            DomainCandidate(
                name=row.name,
                score=score,
                entity_type=_ENTITY_CATEGORY,
                graph_node_id=f"sqns_service_category:{row.name}",
                additional_info=f"priority={row.priority}",
            )
        )

    specialists: list[DomainCandidate] = []
    for row in specialist_rows:
        score = _score_blob(query_norm, row.name, row.specialization, row.information)
        if score <= 0.0:
            continue
        specialization = (row.specialization or "").strip() or None
        information = (row.information or "").strip() or None
        specialists.append(
            DomainCandidate(
                name=row.name,
                score=score,
                entity_type=_ENTITY_SPECIALIST,
                graph_node_id=f"sqns_specialist:{row.external_id}",
                external_id=str(row.external_id),
                additional_info=specialization[:400] if specialization else None,
                information=information[:400] if information else None,
            )
        )

    for row in employee_rows:
        score = _score_blob(query_norm, row.full_name, row.position)
        if score <= 0.0:
            continue
        specialists.append(
            DomainCandidate(
                name=row.full_name,
                score=score,
                entity_type=_ENTITY_EMPLOYEE,
                graph_node_id=f"sqns_employee:{row.external_id}",
                external_id=str(row.external_id),
                additional_info=(row.position or None),
            )
        )

    services = _dedupe_candidates(sorted(services, key=lambda item: item.score, reverse=True))[:max_candidates]
    categories = _dedupe_candidates(sorted(categories, key=lambda item: item.score, reverse=True))[:max_candidates]
    specialists = _dedupe_candidates(sorted(specialists, key=lambda item: item.score, reverse=True))[:max_candidates]
    return services, specialists, categories


async def query_graphrag(
    db: AsyncSession,
    *,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
    query: str,
    focus: Literal["auto", "booking", "general"] = "auto",
    max_candidates: int = 5,
) -> dict[str, Any]:
    """Hybrid search: Neo4j vector+fulltext+graph retrieval + SQNS candidates.

    Flow:
    1. Search Neo4j using HybridGraphRetriever (vector + fulltext + graph augmentation)
    2. Parse results to extract services, specialists, objections, tactics
    3. Search SQNS for additional service/specialist matches
    4. Combine and return structured context with edges for LLM
    """
    from app.services.graph.retriever import get_hybrid_graph_retriever, GraphRetrievalResult

    q = (query or "").strip()
    if not q:
        return {
            "status": "error",
            "message": "Пустой запрос.",
        }

    effective_cap = max(1, min(int(max_candidates or 5), 10))

    # 1. Search Neo4j hybrid retriever
    script_context: list[dict[str, Any]] = []
    graph_retrieval_results: list[GraphRetrievalResult] = []

    try:
        from app.services.tenant_llm_config import get_decrypted_api_key

        retriever = get_hybrid_graph_retriever(agent_id=agent.id, tenant_id=tenant_id)
        openai_api_key = await get_decrypted_api_key(db, tenant_id)
        graph_retrieval_results = await retriever.search(
            query_text=q, top_k=effective_cap, openai_api_key=openai_api_key
        )

        # Build script_context from retriever results
        for r in graph_retrieval_results[:effective_cap]:
            script_context.append({
                "title": r.title,
                "node_label": r.node_label,
                "situation": r.situation,
                "approach": r.approach,
                "phrases": r.phrases,
                "content_text": r.content_text,
                "service_description": r.service_description,
                "service_name": r.service_name,
                "service_external_id": r.service_external_id,
                "objections": r.objections,
                "tactics": r.tactics,
                "score": r.score,
            })
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "hybrid_graph_retriever_failed",
            agent_id=str(agent.id),
            query=q[:100],
            error=str(exc),
        )

    # 2. Build service/specialist candidates from retriever results (embedding-based, not lexical)
    service_candidates: list[DomainCandidate] = []
    specialist_candidates: list[DomainCandidate] = []
    category_candidates: list[DomainCandidate] = []

    seen_svc_ids: set[str] = set()
    seen_sp_ids: set[str] = set()
    for r in graph_retrieval_results:
        if r.node_label == "Service" and r.service_external_id:
            ext_id = str(r.service_external_id)
            if ext_id not in seen_svc_ids:
                seen_svc_ids.add(ext_id)
                service_candidates.append(DomainCandidate(
                    name=r.title,
                    score=r.score,
                    entity_type=_ENTITY_SERVICE,
                    graph_node_id=f"sqns_service:{ext_id}",
                    external_id=ext_id,
                    additional_info=(r.service_description[:200] or None),
                ))
        elif r.node_label == "Specialist":
            for sp in (r.specialists or []):
                ext_id = str(sp.get("external_id", ""))
                if ext_id and ext_id not in seen_sp_ids:
                    seen_sp_ids.add(ext_id)
                    specialist_candidates.append(DomainCandidate(
                        name=sp.get("name", r.title),
                        score=r.score,
                        entity_type=_ENTITY_SPECIALIST,
                        graph_node_id=f"sqns_specialist:{ext_id}",
                        external_id=ext_id,
                        additional_info=(r.specialist_info[:200] or None),
                    ))

    # 3. Determine booking intent and clarification needs
    booking_mode = focus == "booking"
    needs_clarification = booking_mode and len(service_candidates) != 1
    clarify_question = (
        _build_clarify_question(services=service_candidates, specialists=specialist_candidates)
        if booking_mode
        else None
    )

    # 4. Plan next tool call
    next_tool: str | None = None
    suggested_sqns_args: dict[str, Any] | None = None
    if booking_mode and not needs_clarification and service_candidates:
        next_tool = "sqns_find_booking_options"
        suggested_sqns_args = {"service_name": service_candidates[0].name}
        if len(specialist_candidates) == 1:
            suggested_sqns_args["specialist_name"] = specialist_candidates[0].name

    # 5. Build qualification snippets from graph results
    qualification_snippets: list[dict[str, Any]] = []
    for r in graph_retrieval_results[:effective_cap]:
        if r.situation or r.approach:
            qualification_snippets.append({
                "title": r.title,
                "excerpt": (r.situation or r.approach or "")[:250],
                "graph_node_id": r.service_external_id,  # external_id for SQNS reference
            })

    return {
        "status": "ok",
        "focus": focus,
        "has_match": bool(graph_retrieval_results or service_candidates or specialist_candidates or category_candidates),
        "script_context": script_context,
        "service_candidates": _candidates_to_payload(service_candidates),
        "specialist_candidates": _candidates_to_payload(specialist_candidates),
        "category_candidates": _candidates_to_payload(category_candidates),
        "qualification_snippets": qualification_snippets[:effective_cap],
        "needs_clarification": needs_clarification,
        "clarify_question": clarify_question,
        "next_tool": next_tool,
        "suggested_sqns_args": suggested_sqns_args,
        "retrieval_path": "neo4j_hybrid" if graph_retrieval_results else "sqns_tables",
        "graph_workspace_ready": False,  # Not needed with hybrid retriever
        "graph_last_indexed_at": (
            agent.microsoft_graphrag_last_indexed_at.isoformat()
            if getattr(agent, "microsoft_graphrag_last_indexed_at", None) is not None
            else None
        ),
    }


async def build_graphrag_tool(
    *,
    db: AsyncSession,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
) -> PydanticTool:
    async def _query_graphrag(
        query: str,
        focus: Literal["auto", "booking", "general"] | None = "auto",
        max_candidates: int | None = 5,
    ) -> dict[str, Any]:
        return await query_graphrag(
            db,
            settings=settings,
            agent=agent,
            tenant_id=tenant_id,
            query=query,
            focus=focus or "auto",
            max_candidates=int(max_candidates or 5),
        )

    _query_graphrag.__name__ = "query_graphrag"

    description = (agent.microsoft_graphrag_tool_description or "").strip() or DEFAULT_TOOL_DESCRIPTION
    return PydanticTool.from_schema(
        function=_query_graphrag,
        name="query_graphrag",
        description=description,
        json_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Свободный запрос клиента про услуги, специалистов, категории, знания или запись.",
                },
                "focus": {
                    "type": "string",
                    "enum": ["auto", "booking", "general"],
                    "default": "auto",
                    "description": (
                        "auto — обычный режим; booking — если нужно подобрать услугу/специалиста для записи; "
                        "general — если нужен общий поиск по графовому индексу и таблицам."
                    ),
                },
                "max_candidates": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )
