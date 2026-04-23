from __future__ import annotations

from collections import Counter
import json

import networkx as nx
import structlog

from app.core.config import get_settings
from app.services.runtime.model_resolver import resolve_openai_client
from app.services.script_flow_graphrag_schema import (
    GraphCommunity,
    GraphEntity,
    GraphNodeKind,
    GraphRelation,
    StructuredCommunitySummary,
)

logger = structlog.get_logger(__name__)


class ScriptFlowGraphRAGStore:
    async def build_communities(
        self,
        *,
        nodes: list[GraphEntity],
        relations: list[GraphRelation],
        openai_api_key: str | None = None,
        model_name: str | None = None,
    ) -> list[GraphCommunity]:
        graph = nx.Graph()
        for node in nodes:
            graph.add_node(node.graph_node_id, entity_type=node.entity_type, title=node.title)
        for relation in relations:
            graph.add_edge(
                relation.source_graph_node_id,
                relation.target_graph_node_id,
                relation_type=relation.relation_type,
                weight=relation.weight,
            )

        if not graph.nodes:
            return []

        communities: list[GraphCommunity] = []
        for idx, component in enumerate(nx.connected_components(graph), start=1):
            node_ids = sorted(component)
            titles = [graph.nodes[n].get("title") or n for n in node_ids[:4]]
            type_counter = Counter(graph.nodes[n].get("entity_type") or "unknown" for n in node_ids)
            title = " · ".join(titles[:3]) or f"Community {idx}"
            fallback_summary = (
                f"Сообщество объединяет {len(node_ids)} узлов. "
                f"Основные типы: {', '.join(f'{k}×{v}' for k, v in type_counter.most_common(4))}."
            )
            summary_payload = await self._summarize_community(
                node_ids=node_ids,
                titles=titles,
                type_counter=type_counter,
                openai_api_key=openai_api_key,
                model_name=model_name,
            )
            communities.append(
                GraphCommunity(
                    community_key=f"community:{idx}",
                    title=(summary_payload.title if summary_payload else title)[:255],
                    summary=(summary_payload.summary if summary_payload else fallback_summary),
                    node_ids=node_ids,
                    properties={
                        "size": len(node_ids),
                        "top_types": dict(type_counter),
                        "key_points": summary_payload.key_points if summary_payload else [],
                        "recommended_next_step": (
                            summary_payload.recommended_next_step if summary_payload else None
                        ),
                        "summary_source": "llm" if summary_payload else "fallback",
                    },
                )
            )

        community_map = {
            node_id: community.community_key
            for community in communities
            for node_id in community.node_ids
        }
        for node in nodes:
            if node.node_kind == GraphNodeKind.community:
                continue
            node.community_key = community_map.get(node.graph_node_id)

        return communities

    async def _summarize_community(
        self,
        *,
        node_ids: list[str],
        titles: list[str],
        type_counter: Counter,
        openai_api_key: str | None,
        model_name: str | None,
    ) -> StructuredCommunitySummary | None:
        if not (openai_api_key or "").strip():
            return None

        try:
            settings = get_settings()
            client = resolve_openai_client(openai_api_key=openai_api_key)
            effective_model = self._normalize_openai_model(
                model_name
                or settings.script_flow_graphrag_summary_model
                or settings.summary_model
                or settings.pydanticai_default_model
            )

            schema = StructuredCommunitySummary.model_json_schema()
            response = await client.chat.completions.create(
                model=effective_model,
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "script_flow_community_summary",
                        "schema": schema,
                        "strict": True,
                    },
                },
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты summarizer для GraphRAG в премиальных медицинских продажах. "
                            "Сделай короткое, прикладное summary для агента: какие смыслы в сообществе, "
                            "какая тактика и какой следующий шаг рекомендован."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"nodes_count: {len(node_ids)}\n"
                            f"sample_titles: {', '.join(titles[:8])}\n"
                            f"top_types: {json.dumps(dict(type_counter), ensure_ascii=False)}\n"
                            "Верни JSON по schema."
                        ),
                    },
                ],
            )
            content_text = response.choices[0].message.content or "{}"
            return StructuredCommunitySummary.model_validate(json.loads(content_text))
        except Exception as exc:  # noqa: BLE001
            logger.warning("script_flow_graphrag_community_summary_failed", error=str(exc))
            return None

    @staticmethod
    def _normalize_openai_model(model_name: str) -> str:
        raw = (model_name or "").strip()
        if raw.startswith("openai:"):
            return raw.split(":", 1)[1]
        return raw or "gpt-4o-mini"
