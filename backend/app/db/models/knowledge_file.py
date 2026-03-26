from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class KnowledgeFile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_files"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("knowledge_files.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    type: Mapped[str] = mapped_column(
        Enum("folder", "file", name="knowledge_file_type"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    meta_tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    vector_status: Mapped[str] = mapped_column(
        Enum("not_indexed", "indexing", "indexed", "failed", name="knowledge_vector_status"),
        nullable=False,
        default="not_indexed",
        server_default="not_indexed",
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    # Chunking settings are used for chunk-level RAG.
    # For folders, these values act as defaults inherited by descendant files.
    # For files, they may be left NULL and resolved from nearest parent folder.
    chunk_size_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_overlap_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    index_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="knowledge_files")
    parent: Mapped["KnowledgeFile | None"] = relationship(
        "KnowledgeFile",
        remote_side="KnowledgeFile.id",
        back_populates="children",
    )
    children: Mapped[list["KnowledgeFile"]] = relationship(
        "KnowledgeFile",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    # Chunk-level RAG entries. Populated by knowledge indexing jobs.
    chunks: Mapped[list["KnowledgeFileChunk"]] = relationship(
        "KnowledgeFileChunk",
        back_populates="file",
        cascade="all, delete-orphan",
    )
