from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GraphNodeKind(str, Enum):
    canvas = "canvas"
    entity = "entity"
    community = "community"


class GraphEntity(BaseModel):
    graph_node_id: str
    node_kind: GraphNodeKind
    entity_type: str
    title: str
    # OpenAI `strict` structured outputs require every `properties` key to appear in `required`.
    # Represent "optional text" as empty string instead of JSON `null`.
    description: str = ""
    source_node_ids: list[str]
    properties: dict[str, Any]
    # Empty string means "unset" (OpenAI strict mode dislikes optional object keys without defaults).
    community_key: str = ""


class GraphRelation(BaseModel):
    source_graph_node_id: str
    target_graph_node_id: str
    relation_type: str
    weight: float
    properties: dict[str, Any]


class GraphCommunity(BaseModel):
    community_key: str
    title: str
    summary: str = ""
    node_ids: list[str]
    properties: dict[str, Any]


class StructuredCommunitySummary(BaseModel):
    title: str
    summary: str
    key_points: list[str]
    recommended_next_step: str = ""


class StructuredKeyValue(BaseModel):
    """OpenAI `strict` mode rejects `dict[str, Any]` (it becomes `{}` + `additionalProperties: false`).

    Represent arbitrary string metadata as a list of key/value rows instead.
    """

    key: str
    value: str


class StructuredExtractedEntity(BaseModel):
    entity_type: str
    title: str
    description: str = ""
    extra: list[StructuredKeyValue]
    confidence: float


class StructuredExtractedRelation(BaseModel):
    source_ref: str = Field(
        description="Use 'canvas' for relation from current canvas node, or entity title of another extracted entity."
    )
    target_ref: str = Field(description="Entity title of the target")
    relation_type: str
    weight: float
    extra: list[StructuredKeyValue]


class StructuredNodeExtractionResult(BaseModel):
    entities: list[StructuredExtractedEntity]
    relations: list[StructuredExtractedRelation]
    notes: list[str]


class ScriptFlowGraphPreview(BaseModel):
    flow_id: UUID
    flow_version: int
    nodes: list[GraphEntity] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)
    communities: list[GraphCommunity] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)
