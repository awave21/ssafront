from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

KnowledgeItemType = Literal["folder", "file"]
KnowledgeVectorStatus = Literal["not_indexed", "indexing", "indexed", "failed"]


class KnowledgeFileCreate(BaseModel):
    parent_id: UUID | None = None
    type: KnowledgeItemType
    title: str = Field(min_length=1, max_length=255)
    meta_tags: list[str] = Field(default_factory=list)
    content: str = ""
    is_enabled: bool = True
    order_index: int | None = Field(default=None, ge=1)

    @field_validator("meta_tags")
    @classmethod
    def validate_meta_tags(cls, value: list[str]) -> list[str]:
        if len(value) > 30:
            raise ValueError("maximum 30 tags allowed")
        normalized: list[str] = []
        for tag in value:
            clean = str(tag).strip()
            if not clean:
                continue
            normalized.append(clean[:64])
        return normalized


class KnowledgeFileUpdate(BaseModel):
    parent_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    meta_tags: list[str] | None = None
    content: str | None = None
    is_enabled: bool | None = None
    order_index: int | None = Field(default=None, ge=1)
    vector_status: KnowledgeVectorStatus | None = None

    @field_validator("meta_tags")
    @classmethod
    def validate_meta_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        if len(value) > 30:
            raise ValueError("maximum 30 tags allowed")
        normalized: list[str] = []
        for tag in value:
            clean = str(tag).strip()
            if not clean:
                continue
            normalized.append(clean[:64])
        return normalized


class KnowledgeFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    parent_id: UUID | None = None
    type: KnowledgeItemType
    title: str
    meta_tags: list[str]
    content: str
    is_enabled: bool
    vector_status: KnowledgeVectorStatus
    order_index: int
    created_at: datetime
    updated_at: datetime | None = None


class KnowledgeFileIndexResponse(BaseModel):
    job_id: UUID | None = None
    status: Literal["queued", "indexing", "indexed", "failed"] | None = None
    file_id: UUID | None = None
    id: UUID
    vector_status: KnowledgeVectorStatus
    indexed_at: datetime | None = None
    error: str | None = None


class KnowledgeIndexJobStatusRead(BaseModel):
    job_id: UUID
    file_id: UUID
    status: Literal["queued", "indexing", "indexed", "failed"]
    progress: int = Field(ge=0, le=100)
    stage: str | None = None
    chunks_total: int | None = None
    chunks_done: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class KnowledgeFileIndexStatusRead(BaseModel):
    file_id: UUID
    vector_status: KnowledgeVectorStatus
    progress: int = Field(ge=0, le=100)
    job_id: UUID | None = None
    stage: str | None = None
    error: str | None = None
