from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tool import Tool
from app.db.models.tool_parameter import ToolParameter


def _to_parameter_type(schema_type: Any) -> str:
    if schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    return "text"


def _normalize_tool_name(name: str) -> str:
    base = name.strip() or "function_rule_tool"
    safe = "_".join(base.split())
    return safe[:200]


def _extract_tool_description(rule_name: str, condition_config: dict[str, Any]) -> str:
    raw_description = condition_config.get("function_description")
    if isinstance(raw_description, str) and raw_description.strip():
        return raw_description.strip()
    return f"Auto-created from function rule '{rule_name}'."


def _extract_tool_schema(condition_config: dict[str, Any]) -> dict[str, Any]:
    raw_schema = condition_config.get("tool_args_schema")
    if isinstance(raw_schema, str):
        raw_schema = raw_schema.strip()
        if not raw_schema:
            raw_schema = None
        else:
            try:
                raw_schema = json.loads(raw_schema)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="condition_config.tool_args_schema must be valid JSON object",
                ) from exc
    if not isinstance(raw_schema, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="condition_config.tool_args_schema must be an object",
        )
    if raw_schema.get("type") != "object":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="condition_config.tool_args_schema.type must be 'object'",
        )
    properties = raw_schema.get("properties")
    if not isinstance(properties, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="condition_config.tool_args_schema.properties must be an object",
        )
    return raw_schema


async def create_tool_for_function_rule(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    rule_name: str,
    condition_config: dict[str, Any],
) -> Tool:
    candidate_name = _normalize_tool_name(rule_name)
    existing_stmt = select(Tool.id).where(
        Tool.tenant_id == tenant_id,
        Tool.name == candidate_name,
    )
    exists = (await db.execute(existing_stmt)).scalar_one_or_none()
    if exists is not None:
        suffix = uuid4().hex[:8]
        candidate_name = f"{candidate_name}_{suffix}"[:200]

    schema = _extract_tool_schema(condition_config)
    tool = Tool(
        tenant_id=tenant_id,
        name=candidate_name,
        description=_extract_tool_description(rule_name, condition_config),
        input_schema=schema,
        execution_type="internal",
        status="active",
        webhook_scope="tool",
    )
    db.add(tool)
    await db.flush()

    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required_set = set(schema.get("required", []) or [])
    if isinstance(properties, dict):
        for index, (name, prop) in enumerate(properties.items()):
            if not isinstance(name, str):
                continue
            prop_dict = prop if isinstance(prop, dict) else {}
            enum_values = prop_dict.get("enum")
            normalized_enum = [str(item) for item in enum_values] if isinstance(enum_values, list) else None
            db.add(
                ToolParameter(
                    tenant_id=tenant_id,
                    tool_id=tool.id,
                    name=name,
                    type=_to_parameter_type(prop_dict.get("type")),
                    instruction=str(prop_dict.get("description") or f"Parameter '{name}'"),
                    required=name in required_set,
                    is_optional=name not in required_set,
                    enum_values=normalized_enum,
                    x_from_ai=bool(prop_dict.get("x-fromAI", True)),
                    default_value=prop_dict.get("default"),
                    order_index=index,
                )
            )
    return tool
