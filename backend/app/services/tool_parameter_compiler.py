from __future__ import annotations

from typing import Any

from app.schemas.tool_parameter import ToolParameterCreate


TYPE_MAPPING: dict[str, str] = {
    "text": "string",
    "number": "number",
    "boolean": "boolean",
}


def compile_parameters_to_schema(parameters: list[ToolParameterCreate | dict[str, Any]]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    def _normalize_param(raw: ToolParameterCreate | dict[str, Any]) -> ToolParameterCreate:
        if isinstance(raw, ToolParameterCreate):
            return raw
        return ToolParameterCreate(**raw)

    ordered = sorted((_normalize_param(item) for item in parameters), key=lambda item: item.order_index)
    for param in ordered:
        schema_type = TYPE_MAPPING[param.type]
        prop: dict[str, Any] = {
            "type": schema_type,
            "description": param.instruction,
            "x-fromAI": param.x_from_ai,
        }
        if param.enum_values:
            prop["enum"] = param.enum_values
        if param.default_value is not None:
            prop["default"] = param.default_value
        properties[param.name] = prop

        is_required = param.required and not param.is_optional and param.default_value is None
        if is_required:
            required.append(param.name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
