"""
Structured validation for Vue Flow `flow_definition` JSON stored on ScriptFlow.

Keeps permissive extras on nodes/edges so the UI can evolve without frequent schema bumps.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VueFlowNode(BaseModel):
    """Minimal Vue Flow node shape; unknown fields preserved via extra."""

    model_config = ConfigDict(extra="allow")

    id: str
    type: str | None = None
    position: dict[str, Any] | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class VueFlowEdge(BaseModel):
    """Minimal edge shape; Vue Flow emits many optional props."""

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    source: str
    target: str


class FlowDefinitionPayload(BaseModel):
    """
    Top-level graph document. schema_version optional (1 = current frontend shape).
    Planned Wave 7: discriminated ``data`` payloads + schema_version=2 — keep extras via extra=allow until migration.
    Unknown root keys allowed for forward compatibility.
    """

    model_config = ConfigDict(extra="allow")

    schema_version: int | None = None
    nodes: list[VueFlowNode] = Field(default_factory=list)
    edges: list[Any] = Field(default_factory=list)
    viewport: dict[str, Any] | None = None

    @field_validator("edges", mode="before")
    @classmethod
    def edges_must_be_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("edges must be a list")
        return v

    @field_validator("nodes", mode="before")
    @classmethod
    def nodes_must_be_list(cls, v: Any) -> Any:
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("nodes must be a list")
        return v


def validate_flow_definition(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Validate and return a plain dict suitable for JSONB (coerced via model_dump).
    Raises pydantic.ValidationError on failure.
    """
    if not raw:
        return {}
    parsed = FlowDefinitionPayload.model_validate(raw)

    validated_edges: list[dict[str, Any]] = []
    for i, e in enumerate(parsed.edges):
        if not isinstance(e, dict):
            raise ValueError(f"edges[{i}] must be an object")
        validated_edges.append(VueFlowEdge.model_validate(e).model_dump(mode="python"))

    normalized_nodes: list[dict[str, Any]] = []
    for n in parsed.nodes:
        normalized_nodes.append(n.model_dump(mode="python"))

    out = parsed.model_dump(mode="python")
    out["nodes"] = normalized_nodes
    out["edges"] = validated_edges
    if parsed.schema_version is None:
        out.setdefault("schema_version", 2)
    return out
