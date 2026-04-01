from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AttributeType = Literal[
    "text",
    "varchar",
    "integer",
    "float",
    "boolean",
    "date",
    "datetime",
    "timestamp",
    "text_array",
    "number_array",
    "json",
]

class UserTableAttributeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=200)
    attribute_type: AttributeType
    type_config: dict[str, Any] = Field(default_factory=dict)
    is_required: bool = False
    is_searchable: bool = True
    is_unique: bool = False
    order_index: int = 0
    default_value: Any | None = None


class UserTableAttributeUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    name: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_]*$")
    attribute_type: AttributeType | None = None
    type_config: dict[str, Any] | None = None
    is_required: bool | None = None
    is_searchable: bool | None = None
    is_unique: bool | None = None
    order_index: int | None = None
    default_value: Any | None = None


class UserTableAttributeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    table_id: UUID
    name: str
    label: str
    attribute_type: str
    type_config: dict[str, Any]
    is_required: bool
    is_searchable: bool
    is_unique: bool
    order_index: int
    default_value: Any | None = None
    created_at: datetime
    updated_at: datetime | None = None


class UserTableAttributeReorder(BaseModel):
    attribute_ids: list[UUID] = Field(default_factory=list)


class UserTableCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    attributes: list[UserTableAttributeCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_attribute_names(self) -> "UserTableCreate":
        names = [item.name for item in self.attributes]
        if len(names) != len(set(names)):
            raise ValueError("attribute names must be unique within a table")
        return self


class UserTableUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class UserTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None = None
    records_count: int
    created_at: datetime
    updated_at: datetime | None = None
    is_deleted: bool
    attributes: list[UserTableAttributeRead] = Field(default_factory=list)


class UserTableListItem(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    records_count: int
    attributes_count: int
    created_at: datetime
    updated_at: datetime | None = None


class UserTableRecordCreate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    source: str = "admin"


class UserTableRecordUpdate(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class UserTableRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    table_id: UUID
    data: dict[str, Any]
    source: str
    created_at: datetime
    updated_at: datetime | None = None
    is_deleted: bool


class UserTableRecordsListResponse(BaseModel):
    items: list[UserTableRecordRead]
    total: int
    limit: int
    offset: int


class UserTableRecordsBulkCreate(BaseModel):
    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)
    source: str = "import"


class UserTableRecordsBulkCreateResponse(BaseModel):
    created: int
    failed: int
    errors: list[dict[str, Any]] = Field(default_factory=list)


