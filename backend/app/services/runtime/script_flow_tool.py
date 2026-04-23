"""
script_flow_tool.py — runtime tool `search_script_flows`.

Назначение: дать LLM-агенту точечный доступ к экспертным сценариям продаж,
проиндексированным в retrieval-слое, причём с выделением **обязательного вопроса
после тактики** — чтобы агент всегда закрывал ветку уточнением.

Подключается только если у агента есть ≥1 `ScriptFlow` со статусом
`flow_status='published'` и `index_status='indexed'`.

Motive-aware дополнения:
- На вход принимает session_id/tenant для чтения `SessionScriptContext`;
- Делает rerank: де-приоритизирует тактики из `blocked_tactic_ids`,
  буст-ит тактики, закрывающие open_objection_ids;
- Пишет в state `asked_followup_questions` и `shown_proof_ids` на основе
  того, что отдал LLM — так следующий ход не будет дублировать.
"""
from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import structlog
from pydantic_ai.tools import Tool as PydanticTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_kg_entity import AgentKgEntity
from app.db.models.script_flow import ScriptFlow
from app.services.runtime.expertise_policy import (
    build_script_flow_tool_description,
    build_script_flows_prompt_bridge,
)
from app.services.runtime.script_flow_graphrag_runtime import (
    enrich_matches_with_graph_context,
)
from app.services.runtime.motive_state import (
    EMOTIONAL_BUFFER_STATES,
    MotiveState,
    is_state_empty,
    load_motive_state,
    upsert_motive_state,
)
from app.services.runtime.script_flow_graphrag_retriever import (
    ScriptFlowGraphRAGRetriever,
)
from app.services.runtime.script_flow_neo4j_retriever import (
    ScriptFlowNeo4jRetriever,
)
from app.services.runtime.script_flow_retriever import ScriptFlowRetriever

logger = structlog.get_logger(__name__)


DEFAULT_TOOL_DESCRIPTION = build_script_flow_tool_description()


SCRIPT_FLOWS_PROMPT_BRIDGE = build_script_flows_prompt_bridge()


async def agent_has_indexed_flows(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID
) -> bool:
    stmt = (
        select(ScriptFlow.id)
        .where(
            ScriptFlow.agent_id == agent_id,
            ScriptFlow.tenant_id == tenant_id,
            ScriptFlow.flow_status == "published",
            ScriptFlow.index_status == "indexed",
        )
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    return row is not None


# ─── motive-aware обогащение и rerank ────────────────────────────────────

def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


async def _load_agent_entity_index(
    db: AsyncSession, *, agent_id: UUID, tenant_id: UUID
) -> dict[str, Any]:
    """Грузит все KG-сущности агента, строит быстрые индексы по имени/id.

    Возвращает:
    - `by_id` — id → AgentKgEntity
    - `by_type_and_name` — {type → {lower(name) → entity}}
    """
    stmt = select(AgentKgEntity).where(
        AgentKgEntity.agent_id == agent_id,
        AgentKgEntity.tenant_id == tenant_id,
    )
    rows = (await db.execute(stmt)).scalars().all()
    by_id: dict[str, AgentKgEntity] = {str(r.id): r for r in rows}
    by_type_and_name: dict[str, dict[str, AgentKgEntity]] = {}
    for r in rows:
        by_type_and_name.setdefault(r.entity_type, {})[_norm(r.name)] = r
    return {
        "by_id": by_id,
        "by_type_and_name": by_type_and_name,
    }


def _split_constraints_hard_soft(
    constraint_names: list[str], entity_index: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Разделяет список имён Constraint на hard/soft по meta.is_hard."""
    by_name = entity_index["by_type_and_name"].get("constraint") or {}
    hard: list[str] = []
    soft: list[str] = []
    for cn in constraint_names:
        ent = by_name.get(_norm(cn))
        if ent is None:
            soft.append(cn)
            continue
        meta = ent.meta or {}
        if meta.get("is_hard") is True:
            hard.append(cn)
        else:
            soft.append(cn)
    return hard, soft


def _objection_names_to_ids(
    names: list[str], entity_index: dict[str, Any]
) -> list[str]:
    by_name = entity_index["by_type_and_name"].get("objection") or {}
    return [str(by_name[_norm(n)].id) for n in names if _norm(n) in by_name]


def _proof_names_to_ids(
    names: list[str], entity_index: dict[str, Any]
) -> list[str]:
    by_name = entity_index["by_type_and_name"].get("proof") or {}
    return [str(by_name[_norm(n)].id) for n in names if _norm(n) in by_name]


def _rerank_matches(
    matches: list[dict[str, Any]],
    state: MotiveState,
    entity_index: dict[str, Any],
    *,
    score_threshold: float = 0.25,
    max_return: int = 3,
) -> list[dict[str, Any]]:
    """Переупорядочивает матчи на основе state диалога и отсекает шум."""
    open_obj_ids = {
        oid for oid in state.raised_objection_ids
        if oid not in state.closed_objection_ids
    }
    blocked = set(state.blocked_tactic_ids)
    already_asked = {_norm(q) for q in state.asked_followup_questions}
    shown_proofs = set(state.shown_proof_ids)

    # На первом содержательном ходе триггер-узлы полезны как recall-anchor,
    # но обычно хуже готовых question/expertise реплик для ответа клиенту.
    def _node_kind(match: dict[str, Any]) -> str:
        ref = str(match.get("tactic_node_ref") or "").lower()
        title = str(match.get("tactic_title") or "").lower()
        if ref.startswith("bio-t") or title.startswith("запрос:"):
            return "trigger"
        if ref.startswith("bio-q"):
            return "question"
        if ref.startswith("bio-e"):
            return "expertise"
        if ref.startswith("bio-c"):
            return "condition"
        if ref.startswith("bio-end"):
            return "end"
        return "unknown"

    for m in matches:
        score = float(m.get("score", 0.5))
        node_kind = _node_kind(m)
        graph_communities = m.get("graph_communities") if isinstance(m.get("graph_communities"), list) else []
        graph_entities = m.get("graph_entities") if isinstance(m.get("graph_entities"), list) else []
        community_summary = str(m.get("community_summary") or "").strip()
        recommended_next_step = str(m.get("recommended_next_step") or "").strip()
        relation_types = [
            str(v).strip() for v in (m.get("graph_relation_types") or [])
            if str(v).strip()
        ]

        if node_kind == "trigger":
            score *= 0.72
        elif node_kind == "question":
            score *= 1.12
        elif node_kind == "expertise":
            score *= 1.08
        elif node_kind in {"condition", "end"}:
            score *= 0.9

        # Дебуст, если эта же тактика уже не дала сдвига.
        node_ref = m.get("tactic_node_ref")
        if isinstance(node_ref, str) and node_ref in blocked:
            score *= 0.3

        # Буст, если тактика закрывает какое-то ещё открытое возражение.
        obj_ids = _objection_names_to_ids(m.get("objection_names") or [], entity_index)
        if any(oid in open_obj_ids for oid in obj_ids):
            score *= 1.5

        # Дебуст, если её `required_followup_question` уже задавался дословно.
        rfq = m.get("required_followup_question")
        if isinstance(rfq, str) and _norm(rfq) in already_asked:
            score *= 0.5

        # Лёгкий дебуст, если все её proof-ы уже показаны.
        p_ids = _proof_names_to_ids(m.get("proof_names") or [], entity_index)
        if p_ids and all(pid in shown_proofs for pid in p_ids):
            score *= 0.85

        # GraphRAG boost: community-backed matches are usually more semantically grounded
        # than isolated node hits.
        if graph_communities:
            score *= min(1.18, 1.04 + 0.04 * len(graph_communities))
        if community_summary:
            score *= 1.06
        if recommended_next_step:
            score *= 1.04
        if relation_types:
            score *= min(1.08, 1.02 + 0.015 * len(relation_types))
        if graph_entities:
            score *= min(1.07, 1.01 + 0.01 * len(graph_entities))

        # If there are objections in state but graph support is thin, slightly de-prioritize.
        if open_obj_ids and not obj_ids and not graph_communities:
            score *= 0.9

        rationale: list[str] = []
        if graph_communities:
            rationale.append(f"community_support:{len(graph_communities)}")
        if community_summary:
            rationale.append("community_summary")
        if recommended_next_step:
            rationale.append("recommended_next_step")
        if relation_types:
            rationale.append(f"graph_relations:{len(relation_types)}")
        if graph_entities:
            rationale.append(f"graph_entities:{len(graph_entities)}")

        m["score"] = round(score, 4)
        m["_debug_node_kind"] = node_kind
        m["_debug_objection_ids"] = obj_ids
        m["_debug_proof_ids"] = p_ids
        m["_debug_graph_rationale"] = rationale

    reranked = sorted(matches, key=lambda x: -float(x.get("score", 0.0)))
    filtered = [m for m in reranked if float(m.get("score", 0)) >= score_threshold]
    return filtered[:max_return]


def _enrich_match(
    match: dict[str, Any],
    entity_index: dict[str, Any],
) -> dict[str, Any]:
    """Добавляет в match hard/soft constraints и сохраняет node-level style.

    Стиль ответа определяется только полями самой ноды, пришедшими из
    retrieval-ответа. Motive/KG используются для rerank и аналитики, но не
    переопределяют формулировки сценария.
    """
    hard, soft = _split_constraints_hard_soft(
        match.get("constraint_names") or [], entity_index
    )
    out = dict(match)
    out.pop("_debug_objection_ids", None)
    out.pop("_debug_proof_ids", None)
    graph_rationale = list(match.get("_debug_graph_rationale") or [])

    out["communication_style"] = match.get("communication_style")
    out["style_hint"] = None
    out["preferred_phrases"] = list(match.get("preferred_phrases") or [])
    out["forbidden_phrases"] = list(match.get("forbidden_phrases") or [])
    out["hard_constraints"] = hard
    out["soft_constraints"] = soft
    out["graph_rationale"] = graph_rationale
    return out


def _retriever_matches_to_tool_matches(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize ScriptFlowRetriever packets to legacy tool match schema."""
    out: list[dict[str, Any]] = []
    for m in matches:
        meta = m.get("metadata") if isinstance(m.get("metadata"), dict) else {}
        out.append(
            {
                "flow_id": m.get("flow_id"),
                "flow_name": m.get("flow_name"),
                "stage": m.get("stage"),
                "tactic_title": m.get("title") or "",
                "tactic_node_ref": m.get("node_id"),
                "situation": m.get("content_text"),
                "motive_names": [],
                "argument_names": [],
                "proof_names": [],
                "objection_names": [],
                "constraint_names": [],
                "communication_style": meta.get("communication_style"),
                "preferred_phrases": list(meta.get("preferred_phrases") or []),
                "forbidden_phrases": list(meta.get("forbidden_phrases") or []),
                "required_followup_question": meta.get("required_followup_question"),
                "score": float(m.get("score") or 0.0),
            }
        )
    return out


async def build_script_flows_search_tool(
    *,
    db: AsyncSession,
    agent_id: UUID,
    tenant_id: UUID,
    session_id: UUID | None = None,
    openai_api_key: str | None = None,
    strict_entry_default: bool = False,
) -> PydanticTool | None:
    """Возвращает pydantic-ai тул `search_script_flows` или None, если
    у агента нет проиндексированных потоков.

    `openai_api_key` — tenant-специфичный ключ для query-embedding retriever.
    Если `session_id` передан — тул подтягивает motive-state диалога,
    делает rerank и обогащает matches ограничениями.
    """
    effective_key = (openai_api_key or "").strip()
    if not await agent_has_indexed_flows(db, agent_id=agent_id, tenant_id=tenant_id):
        return None

    # entity_index грузим лениво — один раз за тул, с кэшом в замыкании.
    _entity_index_cache: dict[str, Any] = {}

    async def _get_entity_index() -> dict[str, Any]:
        if not _entity_index_cache:
            idx = await _load_agent_entity_index(
                db, agent_id=agent_id, tenant_id=tenant_id
            )
            _entity_index_cache.update(idx)
        return _entity_index_cache

    async def _search_script_flows(
        query: str,
        stage: str | None = None,
        service_id: str | None = None,
        strict_entry: bool | None = None,
        used_followup: str | None = None,
        shown_proof_names: list[str] | None = None,
        blocked_tactic_ref: str | None = None,
    ) -> dict[str, Any]:
        """Searches indexed expert script flows with motive-aware rerank.

        Args:
            query: Natural-language client phrase or intent.
            stage: Optional funnel stage hint (overrides state).
            service_id: Optional SQNS service id to narrow results.
            strict_entry: If true, search only trigger nodes as strict entry points.
                If omitted, uses server default strict_entry_default.
            used_followup: If you JUST asked a follow-up question on a
                previous turn — pass it here so the next search doesn't
                surface the same one.
            shown_proof_names: Proof names you've already cited this session.
            blocked_tactic_ref: Tactic node_ref that didn't move the client
                (e.g. they kept objecting) — will be deprioritized.
        """
        q = query.strip()

        # Загружаем state, если у нас есть session_id.
        state: MotiveState
        if session_id is not None:
            state = await load_motive_state(
                db, session_id=session_id, agent_id=agent_id, tenant_id=tenant_id
            )
        else:
            state = MotiveState.empty(
                session_id=UUID(int=0), agent_id=agent_id, tenant_id=tenant_id
            )

        # Fallback: если diagnose_client_motive ещё не вызывался — используем
        # stage из параметра как минимальный контекст для rerank,
        # чтобы не возвращать нерелевантные тактики из-за пустого state.
        if is_state_empty(state) and stage:
            state = MotiveState.empty(
                session_id=session_id or UUID(int=0),
                agent_id=agent_id,
                tenant_id=tenant_id,
            )
            state.funnel_stage = stage

        # Если LLM сообщает, что только что задала follow-up на прошлом ходе,
        # учитываем это сразу в локальном state до rerank. Иначе текущий вызов
        # ещё не знает про этот вопрос и может вернуть тот же question-узел
        # повторно; сохранение в БД ниже произойдёт уже постфактум.
        if used_followup:
            asked_norm = _norm(used_followup)
            if asked_norm and all(_norm(q) != asked_norm for q in state.asked_followup_questions):
                state.asked_followup_questions = [*state.asked_followup_questions, used_followup]

        # Эмо-буфер: если клиент в эмоции и паузу ещё не давали — тул
        # должен отказать в продаже, а не выдать тактику.
        if (
            state.emotional_state in EMOTIONAL_BUFFER_STATES
            and not state.emotional_pause_used
        ):
            return {
                "status": "emotional_buffer_required",
                "message": (
                    f"Клиент в состоянии {state.emotional_state}. Сначала "
                    "валидируй чувство + задай открытый вопрос, НЕ предлагай "
                    "тактику продажи. На следующем ходу можно вернуться к поиску."
                ),
                "matches": [],
            }

        effective_stage = stage or state.funnel_stage
        retriever = ScriptFlowRetriever(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            openai_api_key=effective_key or None,
        )
        neo4j_retriever = ScriptFlowNeo4jRetriever(
            tenant_id=tenant_id,
            agent_id=agent_id,
        )
        neo4j_packet = await neo4j_retriever.build_context_packet(
            query=query,
            stage=effective_stage,
            service_id=service_id,
        )

        graph_retriever = ScriptFlowGraphRAGRetriever(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            openai_api_key=effective_key or None,
        )
        graph_packet = await graph_retriever.build_context_packet(
            query=query,
            stage=effective_stage,
            service_id=service_id,
        )
        shadow_packet = neo4j_packet if neo4j_packet.matches else graph_packet
        if not shadow_packet.matches:
            shadow_packet = await retriever.build_context_packet(
                query=query,
                stage=effective_stage,
                service_id=service_id,
                entry_only=bool(strict_entry if strict_entry is not None else strict_entry_default),
            )

        matches_raw = _retriever_matches_to_tool_matches(shadow_packet.matches)
        matches_raw, graph_debug = await enrich_matches_with_graph_context(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            matches=matches_raw,
        )
        entity_index = await _get_entity_index()
        reranked = _rerank_matches(matches_raw, state, entity_index)
        enriched = [_enrich_match(m, entity_index) for m in reranked]

        side_effects: dict[str, Any] = {}
        if session_id is not None:
            proof_ids = []
            if shown_proof_names:
                proof_ids = _proof_names_to_ids(shown_proof_names, entity_index)
            asked_list = [used_followup] if used_followup else None
            blocked_list = [blocked_tactic_ref] if blocked_tactic_ref else None
            if proof_ids or asked_list or blocked_list:
                await upsert_motive_state(
                    db,
                    session_id=session_id,
                    agent_id=agent_id,
                    tenant_id=tenant_id,
                    asked_followup_questions=asked_list,
                    shown_proof_ids=proof_ids or None,
                    blocked_tactic_ids=blocked_list,
                )
                await db.commit()
                side_effects = {
                    "recorded_followup": bool(asked_list),
                    "recorded_proofs": len(proof_ids),
                    "recorded_blocked": bool(blocked_list),
                }

        if enriched:
            top = enriched[0]
            logger.info(
                "search_script_flows_match",
                agent_id=str(agent_id),
                session_id=str(session_id) if session_id else None,
                top_score=top.get("score"),
                top_flow=top.get("flow_name"),
                top_tactic=top.get("tactic_title"),
                top_node_ref=top.get("tactic_node_ref"),
                top_stage=top.get("stage"),
                top_communication_style=top.get("communication_style"),
                total_matches=len(enriched),
                funnel_stage=state.funnel_stage,
                emotional_state=state.emotional_state,
                retrieval_engine="script_flow_retriever",
            )
            if session_id is not None:
                _style = {
                    "communication_style": top.get("communication_style"),
                    "preferred_phrases": top.get("preferred_phrases") or [],
                    "forbidden_phrases": top.get("forbidden_phrases") or [],
                    "hard_constraints": top.get("hard_constraints") or [],
                    "required_followup_question": top.get("required_followup_question"),
                    "tactic_title": top.get("tactic_title"),
                    "flow_name": top.get("flow_name"),
                }
                if any([
                    _style["communication_style"],
                    _style["preferred_phrases"],
                    _style["forbidden_phrases"],
                    _style["hard_constraints"],
                ]):
                    try:
                        await upsert_motive_state(
                            db,
                            session_id=session_id,
                            agent_id=agent_id,
                            tenant_id=tenant_id,
                            last_tactic_style=_style,
                        )
                        await db.commit()
                    except Exception:  # noqa: BLE001
                        logger.warning(
                            "search_script_flows_save_style_failed",
                            session_id=str(session_id),
                        )
        else:
            logger.info(
                "search_script_flows_no_matches",
                agent_id=str(agent_id),
                session_id=str(session_id) if session_id else None,
                query=q[:120],
                funnel_stage=state.funnel_stage,
                retrieval_engine="script_flow_retriever",
            )

        out: dict[str, Any] = {
            "status": "ok",
            "matches": enriched,
            "state_snapshot": {
                "emotional_state": state.emotional_state,
                "funnel_stage": state.funnel_stage,
                "open_objection_ids": [
                    x for x in state.raised_objection_ids
                    if x not in state.closed_objection_ids
                ],
                "asked_followup_count": len(state.asked_followup_questions),
            },
        }
        if enriched:
            top_graph_community = enriched[0].get("community_title")
            top_graph_summary = enriched[0].get("community_summary")
            out["graph_context"] = {
                "top_community": top_graph_community,
                "top_community_summary": top_graph_summary,
                "top_graph_rationale": enriched[0].get("graph_rationale") or [],
                "top_recommended_next_step": enriched[0].get("recommended_next_step"),
            }
        if side_effects:
            out["side_effects"] = side_effects
        out["retrieval_engine"] = "script_flow_retriever"
        out["debug"] = {
            **shadow_packet.debug,
            "neo4j_first_used": bool(neo4j_packet.matches),
            "graph_first_used": bool(graph_packet.matches),
            **graph_debug,
        }
        return out

    _search_script_flows.__name__ = "search_script_flows"

    return PydanticTool.from_schema(
        function=_search_script_flows,
        name="search_script_flows",
        description=DEFAULT_TOOL_DESCRIPTION,
        json_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Реплика клиента или краткое описание темы (возражение,"
                        " вопрос, запрос записи)."
                    ),
                },
                "stage": {
                    "type": "string",
                    "description": "Опциональная подсказка по этапу воронки.",
                },
                "service_id": {
                    "type": "string",
                    "description": "Опциональный SQNS service id для фильтра.",
                },
                "strict_entry": {
                    "type": "boolean",
                    "description": (
                        "Если true, искать только entry-узлы (trigger) вместо "
                        "всех searchable-узлов. Если не передан, применяется "
                        "серверный дефолт."
                    ),
                },
                "used_followup": {
                    "type": "string",
                    "description": (
                        "Follow-up, который ты ТОЛЬКО ЧТО задал на прошлом "
                        "ходу — чтобы не повторяться."
                    ),
                },
                "shown_proof_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Proof-имена, которые ты уже цитировал.",
                },
                "blocked_tactic_ref": {
                    "type": "string",
                    "description": (
                        "tactic_node_ref тактики, которая не сработала — "
                        "будет де-приоритизирована."
                    ),
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )
