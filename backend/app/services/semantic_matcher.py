from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


@dataclass
class SemanticMatchResult:
    matched: bool
    score: float
    reason: str
    intent: str | None = None


# ---------------------------------------------------------------------------
# Sync Jaccard-based matcher (fallback / legacy)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Zа-яА-Я0-9_]+", text.lower()) if len(token) > 1}


def _jaccard_score(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = a.intersection(b)
    union = a.union(b)
    if not union:
        return 0.0
    return len(intersection) / len(union)


def semantic_match_text(
    text: str,
    *,
    intents: list[dict] | None = None,
    examples: list[str] | None = None,
    threshold: float = 0.6,
) -> SemanticMatchResult:
    tokens = _tokenize(text)
    best_score = 0.0
    best_reason = "no semantic examples configured"
    best_intent: str | None = None

    if intents:
        for intent in intents:
            intent_name = str(intent.get("name", "unknown_intent"))
            intent_examples = intent.get("examples", [])
            if not isinstance(intent_examples, list):
                continue
            for example in intent_examples:
                if not isinstance(example, str):
                    continue
                score = _jaccard_score(tokens, _tokenize(example))
                if score > best_score:
                    best_score = score
                    best_reason = f"best_intent={intent_name}, best_example={example}"
                    best_intent = intent_name
    if examples:
        for example in examples:
            if not isinstance(example, str):
                continue
            score = _jaccard_score(tokens, _tokenize(example))
            if score > best_score:
                best_score = score
                best_reason = f"best_example={example}"
                best_intent = None

    matched = best_score >= threshold
    return SemanticMatchResult(
        matched=matched,
        score=best_score,
        reason=best_reason,
        intent=best_intent,
    )


# ---------------------------------------------------------------------------
# Async embedding-based matcher (preferred when OpenAI key available)
# ---------------------------------------------------------------------------
#
# Реюзает `create_embedding` из directory/service.py — единая точка биллинга,
# единая модель эмбеддингов (text-embedding-3-small, 1536 dims), тенантный
# ключ через `get_decrypted_api_key`. Никакого параллельного эмбеддера.
#
# Кэш эмбеддингов примеров — в памяти процесса. Ключ = sha1(example_text).
# При двух воркерах gunicorn каждый прогревает свой кэш с первого срабатывания
# правила. Если понадобится общий кэш — сюда легко подставить Redis-обёртку.

_EXAMPLE_EMBEDDING_CACHE: dict[str, list[float]] = {}
_EXAMPLE_CACHE_MAX_ENTRIES = 2048  # мягкий предохранитель


def _cache_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


async def _get_or_compute_example_embedding(
    example_text: str,
    *,
    openai_api_key: str,
    db: AsyncSession | None,
    tenant_id: Any,
    charge_source_id: str | None,
) -> list[float] | None:
    key = _cache_key(example_text)
    cached = _EXAMPLE_EMBEDDING_CACHE.get(key)
    if cached is not None:
        return cached

    # локальный импорт чтобы избежать циклов
    from app.services.directory.service import create_embedding

    emb = await create_embedding(
        example_text,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.rule_semantic_example",
        charge_source_id=charge_source_id,
    )
    if emb is None:
        return None

    # мягкий предохранитель против бесконтрольного роста
    if len(_EXAMPLE_EMBEDDING_CACHE) >= _EXAMPLE_CACHE_MAX_ENTRIES:
        # выкинем произвольные 10% старых записей
        for old_key in list(_EXAMPLE_EMBEDDING_CACHE.keys())[: _EXAMPLE_CACHE_MAX_ENTRIES // 10]:
            _EXAMPLE_EMBEDDING_CACHE.pop(old_key, None)

    _EXAMPLE_EMBEDDING_CACHE[key] = emb
    return emb


async def semantic_match_text_embedded(
    text: str,
    *,
    examples: list[str] | None = None,
    intents: list[dict] | None = None,
    threshold: float = 0.75,
    openai_api_key: str | None,
    db: AsyncSession | None = None,
    tenant_id: Any = None,
    charge_source_id: str | None = None,
) -> SemanticMatchResult:
    """Матчинг по OpenAI-эмбеддингам через cosine similarity.

    Порог по умолчанию 0.75 — типичный для «смыслово одинаковых» коротких фраз
    на text-embedding-3-small. Существенно выше Jaccard-порогов (0.3–0.5).
    """
    # Собираем список примеров из плоского examples и вложенных intents
    all_examples: list[tuple[str, str | None]] = []
    if examples:
        for ex in examples:
            if isinstance(ex, str) and ex.strip():
                all_examples.append((ex.strip(), None))
    if intents:
        for intent in intents:
            if not isinstance(intent, dict):
                continue
            intent_name = str(intent.get("name", "unknown_intent"))
            intent_examples = intent.get("examples") or []
            if not isinstance(intent_examples, list):
                continue
            for ex in intent_examples:
                if isinstance(ex, str) and ex.strip():
                    all_examples.append((ex.strip(), intent_name))

    if not all_examples:
        return SemanticMatchResult(matched=False, score=0.0, reason="no semantic examples configured")

    if not openai_api_key:
        return SemanticMatchResult(
            matched=False, score=0.0,
            reason="embedded matcher requires tenant OpenAI key",
        )

    from app.services.directory.service import create_embedding

    text = (text or "").strip()
    if not text:
        return SemanticMatchResult(matched=False, score=0.0, reason="empty text")

    text_emb = await create_embedding(
        text,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type="embedding.rule_semantic_text",
        charge_source_id=charge_source_id,
    )
    if text_emb is None:
        return SemanticMatchResult(matched=False, score=0.0, reason="text embedding failed")

    best_score = 0.0
    best_example: str | None = None
    best_intent: str | None = None

    for example_text, intent_name in all_examples:
        ex_emb = await _get_or_compute_example_embedding(
            example_text,
            openai_api_key=openai_api_key,
            db=db,
            tenant_id=tenant_id,
            charge_source_id=charge_source_id,
        )
        if ex_emb is None:
            continue
        score = _cosine_similarity(text_emb, ex_emb)
        if score > best_score:
            best_score = score
            best_example = example_text
            best_intent = intent_name

    matched = best_score >= threshold
    reason = f"best_example={best_example}" if best_example else "no matches"
    if best_intent:
        reason = f"best_intent={best_intent}, {reason}"

    return SemanticMatchResult(
        matched=matched,
        score=best_score,
        reason=reason,
        intent=best_intent,
    )
