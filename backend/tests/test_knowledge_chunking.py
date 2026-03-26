from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.knowledge_file import KnowledgeFileCreate, KnowledgeFileUpdate
from app.services.knowledge_chunking import (
    DEFAULT_CHUNK_OVERLAP_CHARS,
    DEFAULT_CHUNK_SIZE_CHARS,
    MAX_CHUNKS_PER_FILE,
    chunk_text_by_chars,
)


def test_chunk_text_respects_max_chunks() -> None:
    text = "x" * (DEFAULT_CHUNK_SIZE_CHARS * (MAX_CHUNKS_PER_FILE + 5))
    chunks = chunk_text_by_chars(
        text,
        chunk_size_chars=DEFAULT_CHUNK_SIZE_CHARS,
        chunk_overlap_chars=DEFAULT_CHUNK_OVERLAP_CHARS,
    )
    assert len(chunks) == MAX_CHUNKS_PER_FILE


def test_chunk_text_overlap_less_than_size_still_progresses() -> None:
    chunks = chunk_text_by_chars("abcdefghij", chunk_size_chars=4, chunk_overlap_chars=3)
    assert len(chunks) >= 2


def test_knowledge_file_create_folder_rejects_overlap_ge_size() -> None:
    with pytest.raises(ValidationError):
        KnowledgeFileCreate(
            type="folder",
            title="F",
            chunk_size_chars=2000,
            chunk_overlap_chars=2000,
        )


def test_knowledge_file_create_folder_accepts_valid_pair() -> None:
    m = KnowledgeFileCreate(
        type="folder",
        title="F",
        chunk_size_chars=2000,
        chunk_overlap_chars=500,
    )
    assert m.chunk_size_chars == 2000


def test_knowledge_file_create_file_ignores_chunk_validation() -> None:
    KnowledgeFileCreate(type="file", title="Doc", content="hi")


def test_knowledge_file_update_both_chunk_fields_invalid() -> None:
    with pytest.raises(ValidationError):
        KnowledgeFileUpdate(chunk_size_chars=500, chunk_overlap_chars=500)
