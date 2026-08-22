"""Статус вызова инструмента вычисляется по ответу, а не пишется константой.

Раньше в tool_call_logs.status всегда попадала строка "success": все 211 вызовов
в базе значились успешными, и отличить сломавшийся инструмент от рабочего по
логу было нельзя. Мягкие отказы рантайм-тулы кладут внутрь ответа.
"""
from __future__ import annotations

from app.services.run_service import _classify_tool_result


def test_error_key_makes_it_an_error() -> None:
    status, payload = _classify_tool_result({"error": "SQNS недоступен"})

    assert status == "error"
    assert payload == {"error": "SQNS недоступен"}


def test_long_error_is_trimmed() -> None:
    _status, payload = _classify_tool_result({"error": "я" * 500})

    assert len(payload["error"]) == 300


def test_no_match_is_empty_not_error() -> None:
    # Поиск отработал, просто ничего не нашёл: лечится наполнением источника.
    status, payload = _classify_tool_result({"status": "no_match", "candidates": []})

    assert status == "empty"
    assert payload == {"tool_status": "no_match"}


def test_empty_slot_list_is_empty() -> None:
    # Так выглядит поиск окон, не нашедший ни одного.
    assert _classify_tool_result({"availableTimeSlots": []})[0] == "empty"


def test_slots_found_is_success() -> None:
    assert _classify_tool_result({"availableTimeSlots": ["10:00", "11:30"]})[0] == "success"


def test_ok_status_is_success() -> None:
    assert _classify_tool_result({"status": "ok", "items": [1]})[0] == "success"


def test_dict_with_content_alongside_empty_list_is_success() -> None:
    # Есть содержательное поле — вызов полезен, даже если список пуст.
    assert _classify_tool_result({"service": "биоревитализация", "slots": []})[0] == "success"


def test_non_dict_payload_is_success() -> None:
    assert _classify_tool_result("готово") == ("success", None)
    assert _classify_tool_result(None) == ("success", None)
