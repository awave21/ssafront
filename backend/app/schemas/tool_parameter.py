from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ParameterType = Literal["text", "number", "boolean"]


class ToolParameterBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: ParameterType
    instruction: str = Field(min_length=1, max_length=500)
    required: bool = True
    is_optional: bool = False
    enum_values: list[str] | None = None
    x_from_ai: bool = True
    default_value: Any | None = None
    order_index: int = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.isidentifier():
            raise ValueError("name must be valid identifier (snake_case)")
        if value.lower() != value:
            raise ValueError("name must be lowercase")
        return value

    @field_validator("enum_values")
    @classmethod
    def validate_enum_values(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            return None
        return cleaned


class ToolParameterCreate(ToolParameterBase):
    pass


class ToolParameterRead(ToolParameterBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    tool_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class ToolParametersUpdateRequest(BaseModel):
    parameters: list[ToolParameterCreate] = Field(default_factory=list)

    @field_validator("parameters")
    @classmethod
    def validate_unique_names(cls, value: list[ToolParameterCreate]) -> list[ToolParameterCreate]:
        names = [p.name for p in value]
        if len(names) != len(set(names)):
            raise ValueError("parameter names must be unique")
        return value


class ToolParametersResponse(BaseModel):
    tool_id: UUID
    parameters: list[ToolParameterRead]
    generated_input_schema: dict[str, Any]


class ToolParametersPreviewRequest(BaseModel):
    parameters: list[ToolParameterCreate] = Field(default_factory=list)


class ToolParametersPreviewResponse(BaseModel):
    input_schema: dict[str, Any]
