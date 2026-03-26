from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.knowledge_chunking import (
    DEFAULT_CHUNK_OVERLAP_CHARS,
    DEFAULT_CHUNK_SIZE_CHARS,
    MAX_CHUNK_SIZE_CHARS,
)

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
    # Chunking settings (chars-based) for folder nodes.
    # If NULL, indexing falls back to defaults or nearest parent folder.
    chunk_size_chars: int | None = Field(default=None, ge=500, le=MAX_CHUNK_SIZE_CHARS)
    chunk_overlap_chars: int | None = Field(default=None, ge=0)

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

    @model_validator(mode="after")
    def validate_folder_chunk_pair(self) -> KnowledgeFileCreate:
        if self.type != "folder":
            return self
        size = self.chunk_size_chars
        overlap = self.chunk_overlap_chars
        if size is None and overlap is None:
            return self
        eff_size = size if size is not None else DEFAULT_CHUNK_SIZE_CHARS
        eff_overlap = overlap if overlap is not None else DEFAULT_CHUNK_OVERLAP_CHARS
        if eff_overlap >= eff_size:
            raise ValueError("chunk_overlap_chars must be less than chunk_size_chars (after applying defaults)")
        return self


class KnowledgeFileUpdate(BaseModel):
    parent_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    meta_tags: list[str] | None = None
    content: str | None = None
    is_enabled: bool | None = None
    order_index: int | None = Field(default=None, ge=1)
    vector_status: KnowledgeVectorStatus | None = None
    chunk_size_chars: int | None = Field(default=None, ge=500, le=MAX_CHUNK_SIZE_CHARS)
    chunk_overlap_chars: int | None = Field(default=None, ge=0)

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

    @model_validator(mode="after")
    def validate_chunk_pair_when_both_explicit(self) -> KnowledgeFileUpdate:
        fs = self.model_fields_set
        if "chunk_size_chars" not in fs and "chunk_overlap_chars" not in fs:
            return self
        size = self.chunk_size_chars
        overlap = self.chunk_overlap_chars
        if size is not None and overlap is not None and overlap >= size:
            raise ValueError("chunk_overlap_chars must be less than chunk_size_chars")
        return self


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
    chunk_size_chars: int | None = None
    chunk_overlap_chars: int | None = None
    # Только для type=file: число строк в knowledge_file_chunks (0 если ещё не индексировали).
    chunks_count: int | None = None
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class KnowledgeFileIndexResponse(BaseModel):
    job_id: UUID | None = None
    status: Literal["queued", "indexing", "indexed", "failed"] | None = None
    progress: int = Field(default=0, ge=0, le=100)
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
    indexed_at: datetime | None = None
    error: str | None = None


class KnowledgeFileIndexStatusRead(BaseModel):
    file_id: UUID
    vector_status: KnowledgeVectorStatus
    progress: int = Field(ge=0, le=100)
    chunks_count: int = Field(default=0, ge=0)
    indexed_at: datetime | None = None
    job_id: UUID | None = None
    stage: str | None = None
    error: str | None = None


class KnowledgeVectorTestChunkRead(BaseModel):
    """Номер в выдаче векторного поиска; тот же N, что в заголовке ### Фрагмент N в промпте к модели."""

    fragment_index: int = Field(ge=1, le=100)
    chunk_id: UUID
    file_id: UUID
    chunk_index: int | None = None
    title: str
    relevance: float
    excerpt: str


class KnowledgeVectorTestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)


class KnowledgeVectorTestResponse(BaseModel):
    """Отладка RAG: чанки из векторного поиска и ответ модели агента только по ним."""

    chunks: list[KnowledgeVectorTestChunkRead]
    answer: str | None = Field(
        default=None,
        description="Ответ модели по чанкам; если чанков нет — текст-подсказка без вызова LLM.",
    )
    answer_error: str | None = None
