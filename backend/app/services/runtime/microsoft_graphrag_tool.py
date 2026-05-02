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
from app.services.graphrag_export.graphrag_preview import (
    agent_graphrag_workspace,
    load_graphrag_preview_from_workspace,
)
from app.services.graphrag_export.graphrag_query_cli import run_graphrag_query
from app.services.runtime.microsoft_graphrag_neo4j_read import search_microsoft_graphrag_neo4j
from app.services.runtime.expertise_policy import build_microsoft_graphrag_tool_description

import structlog

logger = structlog.get_logger(__name__)

_GRAPHRAG_CLI_METHODS = {"basic", "local", "global", "drift"}

DEFAULT_TOOL_DESCRIPTION = build_microsoft_graphrag_tool_description()

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


_SERVICE_CODE_RE = re.compile(r"^[А-ЯA-ZА-Яа-я]\d+[\d.]*\s+")


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


async def query_microsoft_graphrag(
    db: AsyncSession,
    *,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
    query: str,
    focus: Literal["auto", "booking", "general"] = "auto",
    max_candidates: int = 5,
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "status": "error",
            "message": "Пустой запрос.",
        }

    effective_cap = max(1, min(int(max_candidates or 5), 10))
    q_norm = _normalize_lookup_text(q)

    runtime_method = (getattr(settings, "microsoft_graphrag_runtime_method", "substring") or "substring").lower()
    graph_matches: list[dict[str, Any]] = []
    preview_snippets: list[dict[str, Any]] = []
    preview_source = ""

    if runtime_method in _GRAPHRAG_CLI_METHODS:
        ws = agent_graphrag_workspace(settings, tenant_id=tenant_id, agent=agent)
        if ws is not None and ws.is_dir():
            timeout_sec = float(getattr(settings, "microsoft_graphrag_runtime_query_timeout_seconds", 60.0))
            cli_res = await run_graphrag_query(
                db=db,
                settings=settings,
                tenant_id=tenant_id,
                ws=ws,
                question=q,
                method=runtime_method,  # type: ignore[arg-type]
                timeout_sec=timeout_sec,
            )
            if cli_res.get("ok") and cli_res.get("answer"):
                preview_snippets = [{
                    "title": f"GraphRAG {runtime_method}",
                    "excerpt": str(cli_res["answer"]),
                    "graph_node_id": None,
                }]
                preview_source = str(cli_res.get("source") or f"graphrag_{runtime_method}")
            else:
                logger.warning(
                    "runtime_graphrag_cli_fallback",
                    method=runtime_method,
                    error=cli_res.get("error"),
                    agent_id=str(agent.id),
                )
                # Фолбэк на substring-поиск ниже.

    if not preview_source:
        graph_matches, preview_snippets, preview_source = await search_microsoft_graphrag_neo4j(
            tenant_id=tenant_id,
            agent_id=agent.id,
            query_tokens=_query_tokens(q_norm),
            limit=effective_cap,
        )
        if not graph_matches:
            ws_matches, ws_snippets, ws_source = _search_preview_matches(
                settings=settings,
                agent=agent,
                tenant_id=tenant_id,
                query_norm=q_norm,
                max_candidates=effective_cap,
            )
            if ws_matches:
                graph_matches = ws_matches
                preview_snippets = ws_snippets
                preview_source = ws_source
            elif preview_source != "neo4j_graph":
                preview_source = ws_source
    service_candidates, specialist_candidates, category_candidates = await _search_domain_candidates(
        db,
        agent_id=agent.id,
        query_norm=q_norm,
        max_candidates=effective_cap,
    )

    booking_mode = focus == "booking" or (focus == "auto" and _looks_like_booking_intent(q_norm))
    needs_clarification = booking_mode and len(service_candidates) != 1
    clarify_question = (
        _build_clarify_question(services=service_candidates, specialists=specialist_candidates)
        if booking_mode
        else None
    )

    next_tool: str | None = None
    suggested_sqns_args: dict[str, Any] | None = None
    if booking_mode and not needs_clarification and service_candidates:
        next_tool = "sqns_find_booking_options"
        suggested_sqns_args = {"service_name": service_candidates[0].name}
        if len(specialist_candidates) == 1:
            suggested_sqns_args["specialist_name"] = specialist_candidates[0].name

    qualification_snippets = preview_snippets[:]
    if not qualification_snippets:
        for bucket in (service_candidates, specialist_candidates, category_candidates):
            for item in bucket:
                if not item.additional_info:
                    continue
                qualification_snippets.append(
                    {
                        "title": item.name,
                        "excerpt": item.additional_info,
                        "graph_node_id": item.graph_node_id,
                    }
                )
                if len(qualification_snippets) >= effective_cap:
                    break
            if len(qualification_snippets) >= effective_cap:
                break

    retrieval_path = "neo4j_graph+sqns_tables" if preview_source == "neo4j_graph" else (
        "workspace_preview+sqns_tables" if graph_matches else "sqns_tables"
    )
    if preview_source not in {"neo4j_graph", "workspace_parquet", "no_workspace"}:
        retrieval_path = f"{retrieval_path}:{preview_source}"

    return {
        "status": "ok",
        "focus": focus,
        "has_match": bool(graph_matches or service_candidates or specialist_candidates or category_candidates),
        "matches": graph_matches,
        "service_candidates": _candidates_to_payload(service_candidates),
        "specialist_candidates": _candidates_to_payload(specialist_candidates),
        "category_candidates": _candidates_to_payload(category_candidates),
        "qualification_snippets": qualification_snippets[:effective_cap],
        "needs_clarification": needs_clarification,
        "clarify_question": clarify_question,
        "next_tool": next_tool,
        "suggested_sqns_args": suggested_sqns_args,
        "retrieval_path": retrieval_path,
        "graph_workspace_ready": preview_source == "workspace_parquet",
        "graph_last_indexed_at": (
            agent.microsoft_graphrag_last_indexed_at.isoformat()
            if getattr(agent, "microsoft_graphrag_last_indexed_at", None) is not None
            else None
        ),
    }


async def build_microsoft_graphrag_tool(
    *,
    db: AsyncSession,
    settings: Any,
    agent: Agent,
    tenant_id: UUID,
) -> PydanticTool:
    async def _query_microsoft_graphrag(
        query: str,
        focus: Literal["auto", "booking", "general"] | None = "auto",
        max_candidates: int | None = 5,
    ) -> dict[str, Any]:
        return await query_microsoft_graphrag(
            db,
            settings=settings,
            agent=agent,
            tenant_id=tenant_id,
            query=query,
            focus=focus or "auto",
            max_candidates=int(max_candidates or 5),
        )

    _query_microsoft_graphrag.__name__ = "query_microsoft_graphrag"

    description = (agent.microsoft_graphrag_tool_description or "").strip() or DEFAULT_TOOL_DESCRIPTION
    return PydanticTool.from_schema(
        function=_query_microsoft_graphrag,
        name="query_microsoft_graphrag",
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
