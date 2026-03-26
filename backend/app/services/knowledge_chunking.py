from __future__ import annotations

"""Shared chunking constants and text splitting for knowledge file RAG."""

DEFAULT_CHUNK_SIZE_CHARS = 6000
DEFAULT_CHUNK_OVERLAP_CHARS = 1000
MAX_CHUNKS_PER_FILE = 250
MAX_CHUNK_SIZE_CHARS = 50_000


def chunk_text_by_chars(text: str, *, chunk_size_chars: int, chunk_overlap_chars: int) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return []
    if chunk_size_chars <= 0:
        return [normalized[:1_000_000]]
    overlap = max(0, chunk_overlap_chars)
    if overlap >= chunk_size_chars:
        overlap = max(0, chunk_size_chars - 1)
    step = max(1, chunk_size_chars - overlap)

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size_chars, len(normalized))
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if len(chunks) >= MAX_CHUNKS_PER_FILE:
            break
        start += step
    return chunks
