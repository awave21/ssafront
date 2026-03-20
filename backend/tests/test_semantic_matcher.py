from __future__ import annotations

from app.services.semantic_matcher import semantic_match_text


def test_semantic_match_interest_to_service() -> None:
    result = semantic_match_text(
        "Я хочу записаться на услугу массажа",
        intents=[
            {
                "name": "interest_to_service",
                "examples": [
                    "интерес к услуге",
                    "хочу услугу",
                    "запишите на массаж",
                ],
            }
        ],
        threshold=0.1,
    )
    assert result.matched is True
    assert result.intent == "interest_to_service"
    assert result.score >= 0.1


def test_semantic_match_not_enough_signal() -> None:
    result = semantic_match_text(
        "погода сегодня отличная",
        intents=[
            {
                "name": "interest_to_service",
                "examples": ["хочу услугу", "интерес к услуге"],
            }
        ],
        threshold=0.5,
    )
    assert result.matched is False

