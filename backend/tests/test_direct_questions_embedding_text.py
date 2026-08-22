"""Поиск по прямым вопросам: что попадает в вектор и к чему применяется порог.

Два дефекта, зафиксированные этими тестами:
1. В вектор карточки уходил только заголовок — содержимое, где лежит сам ответ,
   в поиске не участвовало вовсе.
2. При включённом реранкинге relevance перезаписывался гибридным score, и порог
   45% означал 69% по косинусу.
"""
from __future__ import annotations

from app.services.direct_questions.crud import (
    MAX_EMBEDDING_CONTENT_CHARS,
    _build_embedding_text,
)
from app.services.direct_questions.retrieval import _rerank_direct_question_candidates


# --- текст для эмбеддинга --------------------------------------------------


def test_embedding_text_keeps_question_form_of_title() -> None:
    # Одно слово даёт слабый вектор, поэтому заголовок дублируется вопросом.
    assert _build_embedding_text("Адрес") == "Адрес. Адрес?"


def test_embedding_text_includes_content() -> None:
    text = _build_embedding_text(
        "Оборудование для эпиляции",
        "Работаем на александритовом лазере Candela, процедура занимает 20 минут",
    )

    assert "александритовом лазере" in text
    assert text.startswith("Оборудование для эпиляции. Оборудование для эпиляции?")


def test_embedding_text_survives_empty_content() -> None:
    assert _build_embedding_text("Цена", "") == "Цена. Цена?"
    assert _build_embedding_text("Цена", "   ") == "Цена. Цена?"


def test_embedding_text_truncates_long_content() -> None:
    # Длинный ответ размывает вектор — карточка начинает находиться на что угодно.
    text = _build_embedding_text("Услуга", "я" * (MAX_EMBEDDING_CONTENT_CHARS + 500))

    assert len(text) < MAX_EMBEDDING_CONTENT_CHARS + 100


def test_embedding_text_strips_trailing_punctuation_from_title() -> None:
    assert _build_embedding_text("Сколько стоит?").startswith("Сколько стоит. Сколько стоит?")


# --- реранкинг -------------------------------------------------------------


def _candidate(title: str, relevance: float) -> dict:
    return {"id": title, "title": title, "relevance": relevance, "match_percent": relevance * 100}


def test_rerank_does_not_touch_relevance() -> None:
    # Порог сравнивается с relevance, поэтому там обязан остаться косинус.
    candidates = [_candidate("режим работы", 0.40), _candidate("адрес клиники", 0.35)]

    reranked = _rerank_direct_question_candidates("во сколько вы работаете", candidates)

    assert {item["title"]: item["relevance"] for item in reranked} == {
        "режим работы": 0.40,
        "адрес клиники": 0.35,
    }


def test_rerank_exposes_its_own_score_separately() -> None:
    candidates = [_candidate("режим работы", 0.40), _candidate("адрес клиники", 0.35)]

    reranked = _rerank_direct_question_candidates("режим работы", candidates)

    assert all("rerank_score" in item for item in reranked)


def test_rerank_reorders_by_lexical_overlap() -> None:
    # У «адрес клиники» косинус выше, но спрашивают дословно про режим работы.
    candidates = [_candidate("адрес клиники", 0.40), _candidate("режим работы", 0.38)]

    reranked = _rerank_direct_question_candidates("режим работы", candidates)

    assert reranked[0]["title"] == "режим работы"


def test_rerank_respects_top_n() -> None:
    candidates = [_candidate(f"вопрос {i}", 0.3 + i / 100) for i in range(5)]

    assert len(_rerank_direct_question_candidates("вопрос", candidates, top_n=2)) == 2
