from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator
import jsonschema


class ToolBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    input_schema: dict[str, Any]
    execution_type: Literal["http_webhook", "internal"] = "http_webhook"
    endpoint: str | None = Field(default=None, max_length=500)
    http_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    auth_type: Literal[
        "none",
        "api_key",
        "bearer_token",
        "basic_auth",
        "custom_header",
        "query_param",
        "oauth2",
        "service",
    ] = "none"
    status: Literal["active", "deprecated"] = "active"
    webhook_scope: Literal["tool", "function_only", "both"] = "tool"
    version: int = 1
    custom_headers: dict[str, str] | None = None
    response_transform: dict[str, Any] | None = None
    parameter_mapping: dict[str, Any] | None = None
    
    @field_validator('input_schema')
    @classmethod
    def validate_json_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """
        Валидировать JSON Schema для параметров тула.
        
        Проверяет:
        1. Валидность JSON Schema (Draft 2020-12)
        2. Что type = 'object' (требование pydantic-ai)
        3. Что имена свойств - валидные Python идентификаторы
        """
        if not isinstance(v, dict):
            raise ValueError("input_schema must be a dictionary")
        
        # Проверить, что это валидная JSON Schema
        try:
            jsonschema.Draft202012Validator.check_schema(v)
        except jsonschema.SchemaError as e:
            raise ValueError(f"Invalid JSON Schema: {e.message}")
        
        # Проверить, что type='object' (требование pydantic-ai для tool parameters)
        schema_type = v.get('type')
        if schema_type != 'object':
            raise ValueError(
                f"Tool input_schema must have type='object', got type='{schema_type}'. "
                "Pydantic AI tools require object schema for parameters."
            )
        
        # Проверить, что property names - валидные идентификаторы
        properties = v.get('properties', {})
        if not isinstance(properties, dict):
            raise ValueError("input_schema properties must be a dictionary")
        
        for prop_name in properties:
            if not isinstance(prop_name, str):
                raise ValueError(f"Property name must be string, got {type(prop_name)}")
            if not prop_name.isidentifier():
                raise ValueError(
                    f"Invalid property name '{prop_name}'. "
                    "Property names must be valid Python identifiers (no spaces, special chars, etc)."
                )
        
        # --- Валидация x-fromAI ---
        has_from_ai = False
        for prop_name, prop_def in properties.items():
            if not isinstance(prop_def, dict):
                continue
            from_ai = prop_def.get("x-fromAI")
            if from_ai is not None:
                has_from_ai = True
                if not isinstance(from_ai, bool):
                    raise ValueError(
                        f"Property '{prop_name}': x-fromAI must be boolean, "
                        f"got {type(from_ai).__name__}"
                    )

        # Backward compatibility:
        # legacy tools may contain static properties without defaults.
        # We keep x-fromAI type checks but do not hard-fail on missing defaults.
        
        return v


class ToolCreate(ToolBase):
    agent_id: UUID | None = Field(
        default=None,
        description="Опционально: если передан agent_id, tool будет автоматически привязан к агенту",
    )


class ToolUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    execution_type: Literal["http_webhook", "internal"] | None = None
    endpoint: str | None = Field(default=None, max_length=500)
    http_method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] | None = None
    auth_type: Literal[
        "none",
        "api_key",
        "bearer_token",
        "basic_auth",
        "custom_header",
        "query_param",
        "oauth2",
        "service",
    ] | None = None
    status: Literal["active", "deprecated"] | None = None
    webhook_scope: Literal["tool", "function_only", "both"] | None = None
    version: int | None = None
    custom_headers: dict[str, str] | None = None
    response_transform: dict[str, Any] | None = None
    parameter_mapping: dict[str, Any] | None = None


class ToolRead(ToolBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class ToolTestRequest(BaseModel):
    """Запрос на тестовый вызов tool."""
    args: dict[str, Any] = Field(default_factory=dict)
    # Для тестирования до сохранения (inline):
    endpoint: str | None = None
    http_method: str = "POST"
    input_schema: dict[str, Any] | None = None
    auth_type: str = "none"
    credential_id: UUID | None = None
    custom_headers: dict[str, str] | None = None
    response_transform: dict[str, Any] | None = None
    parameter_mapping: dict[str, Any] | None = None


class ToolTestResponse(BaseModel):
    """Результат тестового вызова tool."""
    status_code: int
    latency_ms: int
    response_headers: dict[str, str]
    raw_body: Any
    transformed_body: Any | None = None
    raw_size_bytes: int
    transformed_size_bytes: int | None = None
    error: str | None = None
    request_url: str
    request_method: str
