from __future__ import annotations

from collections import defaultdict
import json
import re
from typing import Any

import structlog

from app.core.config import get_settings
from app.services.runtime.model_resolver import resolve_openai_client
from app.services.script_flow_compiler import (
    _condition_handle_map_from_data,
    _edge_label,
    _node_title,
    _node_type,
    _str,
    highlight_lookup_hints,
    substitute_flow_variables,
)
from app.services.script_flow_graphrag_schema import (
    GraphEntity,
    GraphNodeKind,
    GraphRelation,
    StructuredNodeExtractionResult,
)

logger = structlog.get_logger(__name__)


_KEYWORD_MAP: dict[str, tuple[str, str]] = {
    "дорог": ("objection", "Возражение по цене"),
    "цен": ("objection", "Возражение по цене"),
    "подума": ("objection", "Пауза / подумаю"),
    "сравни": ("objection", "Сравнение с альтернативой"),
    "страх": ("concern", "Страх клиента"),
    "бою": ("concern", "Страх клиента"),
    "боль": ("concern", "Опасение боли"),
    "безопас": ("trust_signal", "Безопасность"),
    "врач": ("specialist", "Специалист / врач"),
    "доктор": ("specialist", "Специалист / врач"),
    "опыт": ("trust_signal", "Опыт специалиста"),
    "сертифик": ("proof", "Сертификаты / квалификация"),
    "результат": ("proof", "Ожидаемый результат"),
    "преми": ("persona", "Премиальный клиент"),
    "деликат": ("tactic", "Деликатная подача"),
    "мягк": ("tactic", "Мягкое закрытие"),
    "запис": ("outcome", "Запись на консультацию"),
}


def _resolved_text(data: dict[str, Any], variables: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in (
        "situation",
        "why_it_works",
        "approach",
        "good_question",
        "watch_out",
        "when_relevant",
        "why_we_ask",
        "routing_hint",
        "transition_phrase",
        "trigger_situation",
        "rule_condition",
        "rule_action",
        "final_action",
    ):
        value = _str(data.get(key))
        if value:
            chunks.append(value)
    for key in (
        "example_phrases",
        "alternative_phrasings",
        "preferred_phrases",
        "forbidden_phrases",
        "client_phrase_examples",
        "keyword_hints",
    ):
        raw = data.get(key)
        if isinstance(raw, list):
            vals = [str(v).strip() for v in raw if str(v).strip()]
            if vals:
                chunks.extend(vals)
    text = "\n".join(chunks).strip()
    if not text:
        return ""
    return highlight_lookup_hints(substitute_flow_variables(text, variables))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9а-яё]+", "-", value.lower()).strip("-") or "item"


def _append_unique_entity(dst: list[GraphEntity], seen: set[str], entity: GraphEntity) -> None:
    if entity.graph_node_id in seen:
        return
    seen.add(entity.graph_node_id)
    dst.append(entity)


def _append_unique_relation(dst: list[GraphRelation], seen: set[tuple[str, str, str]], relation: GraphRelation) -> None:
    key = (relation.source_graph_node_id, relation.target_graph_node_id, relation.relation_type)
    if key in seen:
        return
    seen.add(key)
    dst.append(relation)


class ScriptFlowGraphRAGExtractor:
    async def extract(
        self,
        *,
        flow_definition: dict[str, Any],
        flow_metadata: dict[str, Any],
        openai_api_key: str | None = None,
        model_name: str | None = None,
    ) -> tuple[list[GraphEntity], list[GraphRelation], dict[str, Any]]:
        variables = flow_metadata.get("variables") or {}
        nodes = flow_definition.get("nodes") if isinstance(flow_definition.get("nodes"), list) else []
        edges = flow_definition.get("edges") if isinstance(flow_definition.get("edges"), list) else []

        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []
        seen_entities: set[str] = set()
        seen_relations: set[tuple[str, str, str]] = set()
        node_type_counts: dict[str, int] = defaultdict(int)
        semantic_counts: dict[str, int] = defaultdict(int)

        node_map: dict[str, dict[str, Any]] = {}
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "").strip()
            if node_id:
                node_map[node_id] = node

        llm_enabled = bool((openai_api_key or "").strip())
        extraction_mode = "llm_structured" if llm_enabled else "heuristic_fallback"
        llm_ok_nodes = 0
        llm_failed_nodes = 0

        for node_id, node in node_map.items():
            data = node.get("data") if isinstance(node.get("data"), dict) else {}
            node_type = _node_type(node)
            node_type_counts[node_type] += 1
            title = _node_title(node)
            stage = _str(data.get("stage"))
            content = _resolved_text(data, variables)

            _append_unique_entity(
                entities,
                seen_entities,
                GraphEntity(
                    graph_node_id=f"canvas:{node_id}",
                    node_kind=GraphNodeKind.canvas,
                    entity_type=node_type or "script_node",
                    title=title,
                    description=content or title,
                    source_node_ids=[node_id],
                    properties={
                        "node_id": node_id,
                        "node_type": node_type,
                        "stage": stage or None,
                    },
                ),
            )

            if stage:
                stage_id = f"stage:{_slug(stage)}"
                _append_unique_entity(
                    entities,
                    seen_entities,
                    GraphEntity(
                        graph_node_id=stage_id,
                        node_kind=GraphNodeKind.entity,
                        entity_type="stage",
                        title=stage,
                        description=f"Этап диалога: {stage}",
                        source_node_ids=[node_id],
                        properties={"stage": stage},
                    ),
                )
                _append_unique_relation(
                    relations,
                    seen_relations,
                    GraphRelation(
                        source_graph_node_id=f"canvas:{node_id}",
                        target_graph_node_id=stage_id,
                        relation_type="occurs_at_stage",
                        properties={"source": "node.stage"},
                    ),
                )

            for var_name, binding in variables.items():
                var_id = f"variable:{var_name}"
                source_type = binding.get("source_type") if isinstance(binding, dict) else "static"
                _append_unique_entity(
                    entities,
                    seen_entities,
                    GraphEntity(
                        graph_node_id=var_id,
                        node_kind=GraphNodeKind.entity,
                        entity_type="variable",
                        title=var_name.replace("_", " "),
                        description=f"Динамическая переменная ({source_type})",
                        properties={"name": var_name, "source_type": source_type},
                    ),
                )
                if f"{{{{{var_name}}}}}" in str(data) or var_name in content:
                    _append_unique_relation(
                        relations,
                        seen_relations,
                        GraphRelation(
                            source_graph_node_id=f"canvas:{node_id}",
                            target_graph_node_id=var_id,
                            relation_type="uses_variable",
                            properties={"source": "flow_metadata.variables"},
                        ),
                    )

            kg_links = data.get("kg_links") if isinstance(data.get("kg_links"), dict) else {}
            for field, relation_type, entity_type in (
                ("motive_ids", "motivated_by", "motive"),
                ("argument_ids", "argues_with", "proof"),
                ("proof_ids", "supported_by_proof", "proof"),
                ("objection_ids", "handles_objection", "objection"),
                ("constraint_ids", "blocked_by_constraint", "constraint"),
            ):
                raw = kg_links.get(field)
                if not isinstance(raw, list):
                    continue
                for item in raw:
                    item_id = str(item).strip()
                    if not item_id:
                        continue
                    graph_node_id = f"library:{entity_type}:{item_id}"
                    _append_unique_entity(
                        entities,
                        seen_entities,
                        GraphEntity(
                            graph_node_id=graph_node_id,
                            node_kind=GraphNodeKind.entity,
                            entity_type=entity_type,
                            title=item_id,
                            description=f"Справочная сущность {entity_type}: {item_id}",
                            source_node_ids=[node_id],
                            properties={"library_id": item_id, "field": field},
                        ),
                    )
                    _append_unique_relation(
                        relations,
                        seen_relations,
                        GraphRelation(
                            source_graph_node_id=f"canvas:{node_id}",
                            target_graph_node_id=graph_node_id,
                            relation_type=relation_type,
                            properties={"source": field},
                        ),
                    )

            llm_result = await self._extract_node_semantics(
                node_id=node_id,
                node_type=node_type,
                title=title,
                stage=stage,
                content=content,
                openai_api_key=openai_api_key,
                model_name=model_name,
            )

            if llm_result is None:
                llm_failed_nodes += 1
                if not llm_enabled:
                    low_text = f"{title}\n{content}".lower()
                    for keyword, (entity_type, label) in _KEYWORD_MAP.items():
                        if keyword not in low_text:
                            continue
                        semantic_counts[entity_type] += 1
                        graph_node_id = f"{entity_type}:{_slug(label)}"
                        _append_unique_entity(
                            entities,
                            seen_entities,
                            GraphEntity(
                                graph_node_id=graph_node_id,
                                node_kind=GraphNodeKind.entity,
                                entity_type=entity_type,
                                title=label,
                                description=f"Автоизвлечённая доменная сущность: {label}",
                                source_node_ids=[node_id],
                                properties={"keyword": keyword, "source": "heuristic_extractor"},
                            ),
                        )
                        relation_type = {
                            "objection": "handles_objection",
                            "concern": "addresses_concern",
                            "tactic": "uses_tactic",
                            "trust_signal": "supports_trust",
                            "specialist": "references_specialist",
                            "proof": "supported_by_proof",
                            "outcome": "leads_to_outcome",
                            "persona": "relevant_for_persona",
                        }.get(entity_type, "relates_to")
                        _append_unique_relation(
                            relations,
                            seen_relations,
                            GraphRelation(
                                source_graph_node_id=f"canvas:{node_id}",
                                target_graph_node_id=graph_node_id,
                                relation_type=relation_type,
                                properties={"source": "keyword_heuristic", "keyword": keyword},
                            ),
                        )
            else:
                llm_ok_nodes += 1
                entity_ref_map: dict[str, str] = {"canvas": f"canvas:{node_id}"}
                for item in llm_result.entities:
                    semantic_counts[item.entity_type] += 1
                    graph_node_id = f"{item.entity_type}:{_slug(item.title)}"
                    entity_ref_map[item.title.strip().lower()] = graph_node_id
                    _append_unique_entity(
                        entities,
                        seen_entities,
                        GraphEntity(
                            graph_node_id=graph_node_id,
                            node_kind=GraphNodeKind.entity,
                            entity_type=item.entity_type,
                            title=item.title,
                            description=item.description,
                            source_node_ids=[node_id],
                            properties={
                                **(item.properties or {}),
                                "confidence": item.confidence,
                                "source": "llm_structured_extraction",
                            },
                        ),
                    )

                for rel in llm_result.relations:
                    src_ref = rel.source_ref.strip().lower()
                    tgt_ref = rel.target_ref.strip().lower()
                    source_graph_node_id = entity_ref_map.get(src_ref) or (f"canvas:{node_id}" if src_ref == "canvas" else None)
                    target_graph_node_id = entity_ref_map.get(tgt_ref)
                    if not source_graph_node_id or not target_graph_node_id:
                        continue
                    _append_unique_relation(
                        relations,
                        seen_relations,
                        GraphRelation(
                            source_graph_node_id=source_graph_node_id,
                            target_graph_node_id=target_graph_node_id,
                            relation_type=rel.relation_type,
                            weight=rel.weight,
                            properties={**(rel.properties or {}), "source": "llm_structured_extraction"},
                        ),
                    )

        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source") or "").strip()
            target = str(edge.get("target") or "").strip()
            if not source or not target or source not in node_map or target not in node_map:
                continue
            source_handle = str(edge.get("sourceHandle") or edge.get("source_handle") or "").strip()
            branch_label = _edge_label(edge).strip()
            if not branch_label and _node_type(node_map[source]) == "condition":
                handle_map = _condition_handle_map_from_data(node_map[source].get("data") or {})
                branch_label = handle_map.get(source_handle, "")
            _append_unique_relation(
                relations,
                seen_relations,
                GraphRelation(
                    source_graph_node_id=f"canvas:{source}",
                    target_graph_node_id=f"canvas:{target}",
                    relation_type="next_step_to",
                    properties={"branch_label": branch_label or None, "source_handle": source_handle or None},
                ),
            )

        debug = {
            "extraction_mode": extraction_mode,
            "llm_ok_nodes": llm_ok_nodes,
            "llm_failed_nodes": llm_failed_nodes,
            "node_type_counts": dict(node_type_counts),
            "semantic_counts": dict(semantic_counts),
            "entity_count": len(entities),
            "relation_count": len(relations),
        }
        return entities, relations, debug

    async def _extract_node_semantics(
        self,
        *,
        node_id: str,
        node_type: str,
        title: str,
        stage: str,
        content: str,
        openai_api_key: str | None,
        model_name: str | None,
    ) -> StructuredNodeExtractionResult | None:
        if not (openai_api_key or "").strip() or not content.strip():
            return None

        settings = get_settings()
        client = resolve_openai_client(openai_api_key=openai_api_key)
        effective_model = self._normalize_openai_model(
            model_name
            or settings.script_flow_graphrag_extraction_model
            or settings.summary_model
            or settings.pydanticai_default_model
        )

        system_prompt = (
            "Ты извлекаешь knowledge graph из сценариев продаж для премиальной медицинской клиники. "
            "Нужно строго вернуть JSON по schema. Извлекай только сущности и связи, которые явно полезны "
            "для поведения sales-агента в медицинской отрасли. Не выдумывай факты. "
            "Используй только типы сущностей: stage, objection, concern, tactic, trust_signal, specialist, "
            "service, proof, constraint, motive, outcome, persona. "
            "Используй только типы связей: handles_objection, addresses_concern, uses_tactic, supports_trust, "
            "references_specialist, references_service, supported_by_proof, blocked_by_constraint, "
            "leads_to_outcome, relevant_for_persona, motivated_by, occurs_at_stage, next_step_to, relates_to. "
            "source_ref='canvas' означает связь от текущего узла канваса. target_ref и source_ref для других "
            "сущностей должны совпадать с title сущности в entities."
        )
        user_prompt = (
            f"node_id: {node_id}\n"
            f"node_type: {node_type}\n"
            f"title: {title}\n"
            f"stage: {stage or '-'}\n"
            "content:\n"
            f"{content}\n\n"
            "Верни только значимые для GraphRAG сущности и связи. Если сущностей нет — верни пустые списки."
        )

        schema = StructuredNodeExtractionResult.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "script_flow_node_extraction",
                "schema": schema,
                "strict": True,
            },
        }

        try:
            response = await client.chat.completions.create(
                model=effective_model,
                temperature=0,
                response_format=response_format,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            content_text = response.choices[0].message.content or "{}"
            parsed = StructuredNodeExtractionResult.model_validate(json.loads(content_text))
            return parsed
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "script_flow_graphrag_llm_extraction_failed",
                node_id=node_id,
                model=effective_model,
                error=str(exc),
            )
            return None

    @staticmethod
    def _normalize_openai_model(model_name: str) -> str:
        raw = (model_name or "").strip()
        if raw.startswith("openai:"):
            return raw.split(":", 1)[1]
        return raw or "gpt-4o-mini"
