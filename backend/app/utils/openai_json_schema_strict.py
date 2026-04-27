"""Helpers for OpenAI `response_format` JSON schemas with `strict: true`.

OpenAI requires `additionalProperties: false` on object schemas (including nested).
Pydantic `model_json_schema()` may omit this field on some nodes, which yields 400:

"Invalid schema for response_format ... 'additionalProperties' is required to be supplied and to be false."
"""

from __future__ import annotations

from typing import Any


def openai_strict_json_schema(schema: Any) -> dict[str, Any]:
    """Return a deep-copied schema safe for OpenAI strict structured outputs."""
    normalized = _normalize_schema(schema)
    _enforce_additional_properties_false(normalized)
    _ensure_required_object_properties(normalized)
    if not isinstance(normalized, dict):
        return {}
    return normalized


def _normalize_schema(schema: Any) -> Any:
    import copy

    return copy.deepcopy(schema)


def _enforce_additional_properties_false(node: Any) -> None:
    if isinstance(node, dict):
        t = node.get("type")
        if isinstance(t, list):
            # Rare, but JSON Schema allows `type` as a list.
            is_object = "object" in [x for x in t if isinstance(x, str)]
        else:
            is_object = t == "object"

        if is_object:
            # OpenAI strict mode rejects missing OR permissive additionalProperties.
            ap = node.get("additionalProperties", None)
            if ap is True or ap == {} or ap is None:
                node["additionalProperties"] = False
            elif isinstance(ap, dict):
                # If additionalProperties is a schema object, normalize it too.
                _enforce_additional_properties_false(ap)

        # Common JSON-schema containers
        for key in (
            "properties",
            "patternProperties",
            "definitions",
            "$defs",
        ):
            child = node.get(key)
            if isinstance(child, dict):
                for v in child.values():
                    _enforce_additional_properties_false(v)

        for key in ("prefixItems",):
            child = node.get(key)
            if isinstance(child, list):
                for v in child:
                    _enforce_additional_properties_false(v)

        for key in ("items", "not"):
            child = node.get(key)
            if isinstance(child, (dict, list)):
                _enforce_additional_properties_false(child)

        # `additionalProperties` may be a nested object schema; it is NOT a sibling key under `properties`.
        ap_child = node.get("additionalProperties")
        if isinstance(ap_child, dict):
            _enforce_additional_properties_false(ap_child)

        for combiner in ("oneOf", "anyOf", "allOf"):
            children = node.get(combiner)
            if isinstance(children, list):
                for c in children:
                    _enforce_additional_properties_false(c)

        # Some schemas use conditional keywords
        for key in ("if", "then", "else"):
            child = node.get(key)
            if isinstance(child, dict):
                _enforce_additional_properties_false(child)

    elif isinstance(node, list):
        for item in node:
            _enforce_additional_properties_false(item)


def _ensure_required_object_properties(node: Any) -> None:
    """OpenAI strict mode requires `required` to list every key in `properties` for object schemas."""

    def _walk(n: Any) -> None:
        if isinstance(n, dict):
            t = n.get("type")
            if isinstance(t, list):
                is_object = "object" in [x for x in t if isinstance(x, str)]
            else:
                is_object = t == "object"

            props = n.get("properties")
            if is_object and isinstance(props, dict) and props:
                n["required"] = list(props.keys())

            for key in (
                "properties",
                "patternProperties",
                "definitions",
                "$defs",
            ):
                child = n.get(key)
                if isinstance(child, dict):
                    for v in child.values():
                        _walk(v)

            for key in ("prefixItems",):
                child = n.get(key)
                if isinstance(child, list):
                    for v in child:
                        _walk(v)

            for key in ("items", "not"):
                child = n.get(key)
                if isinstance(child, (dict, list)):
                    _walk(child)

            ap_child = n.get("additionalProperties")
            if isinstance(ap_child, dict):
                _walk(ap_child)

            for combiner in ("oneOf", "anyOf", "allOf"):
                children = n.get(combiner)
                if isinstance(children, list):
                    for c in children:
                        _walk(c)

            for key in ("if", "then", "else"):
                child = n.get(key)
                if isinstance(child, dict):
                    _walk(child)
        elif isinstance(n, list):
            for item in n:
                _walk(item)

    _walk(node)
