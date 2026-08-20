"""Расписание правил: редактор и раннер писали и читали разные ключи.

Форма сценария сохраняет start_time/end_time и weekdays, а раннер читал
start/end и days. Из-за этого условие «по времени» срабатывало круглосуточно
(пустое окно подставляло 00:00–23:59), а «по дням недели» не срабатывало
никогда. Тесты фиксируют оба написания и отсутствие окна.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.function_rules_runtime import (
    _evaluate_schedule_time,
    _evaluate_schedule_weekday,
)

# Часовой пояс фиксируем: иначе тест зависит от того, где крутится CI.
CONTEXT = {"agent_timezone": "UTC"}
WHOLE_DAY = ("00:00", "23:59")


def _today() -> int:
    return datetime.now(ZoneInfo("UTC")).weekday()


# --- окно времени ----------------------------------------------------------


def test_schedule_time_reads_runner_spelling() -> None:
    start, end = WHOLE_DAY
    result = _evaluate_schedule_time({"start": start, "end": end}, CONTEXT)

    assert result.matched is True


def test_schedule_time_reads_editor_spelling() -> None:
    # Так пишет редактор сценария — раньше это окно игнорировалось.
    start, end = WHOLE_DAY
    result = _evaluate_schedule_time({"start_time": start, "end_time": end}, CONTEXT)

    assert result.matched is True


def test_schedule_time_without_window_does_not_match() -> None:
    # Ключевая правка: пустая настройка больше не означает «круглосуточно».
    result = _evaluate_schedule_time({}, CONTEXT)

    assert result.matched is False
    assert result.reason == "schedule_time missing window"


def test_schedule_time_ignores_blank_values() -> None:
    result = _evaluate_schedule_time({"start_time": "", "end_time": ""}, CONTEXT)

    assert result.matched is False


def test_schedule_time_prefers_explicit_start_over_editor_key() -> None:
    # Если по недосмотру заполнены оба, выигрывает каноническое написание.
    result = _evaluate_schedule_time(
        {"start": "00:00", "end": "23:59", "start_time": "05:00", "end_time": "05:01"},
        CONTEXT,
    )

    assert result.matched is True


# --- дни недели ------------------------------------------------------------


def test_schedule_weekday_reads_runner_spelling() -> None:
    result = _evaluate_schedule_weekday({"days": [_today()]}, CONTEXT)

    assert result.matched is True


def test_schedule_weekday_reads_editor_spelling() -> None:
    # Так пишет редактор — раньше правило не срабатывало ни в один день.
    result = _evaluate_schedule_weekday({"weekdays": [_today()]}, CONTEXT)

    assert result.matched is True


def test_schedule_weekday_other_days_do_not_match() -> None:
    others = [day for day in range(7) if day != _today()]
    result = _evaluate_schedule_weekday({"weekdays": others}, CONTEXT)

    assert result.matched is False


def test_schedule_weekday_without_days_does_not_match() -> None:
    assert _evaluate_schedule_weekday({}, CONTEXT).matched is False
    assert _evaluate_schedule_weekday({"weekdays": []}, CONTEXT).matched is False
