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
    description: str | None = None
    source_node_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    community_key: str | None = None


class GraphRelation(BaseModel):
    source_graph_node_id: str
    target_graph_node_id: str
    relation_type: str
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphCommunity(BaseModel):
    community_key: str
    title: str
    summary: str | None = None
    node_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class StructuredCommunitySummary(BaseModel):
    title: str
    summary: str
    key_points: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None


class StructuredExtractedEntity(BaseModel):
    entity_type: str
    title: str
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.8


class StructuredExtractedRelation(BaseModel):
    source_ref: str = Field(
        description="Use 'canvas' for relation from current canvas node, or entity title of another extracted entity."
    )
    target_ref: str = Field(description="Entity title of the target")
    relation_type: str
    weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class StructuredNodeExtractionResult(BaseModel):
    entities: list[StructuredExtractedEntity] = Field(default_factory=list)
    relations: list[StructuredExtractedRelation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ScriptFlowGraphPreview(BaseModel):
    flow_id: UUID
    flow_version: int
    nodes: list[GraphEntity] = Field(default_factory=list)
    relations: list[GraphRelation] = Field(default_factory=list)
    communities: list[GraphCommunity] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)
