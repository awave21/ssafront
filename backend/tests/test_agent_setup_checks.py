"""Проверка настроек агента: находки считает код, а не модель."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.services.agent_assistant.checks import Finding, _check_action, render_checks


def _table(name: str, columns: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        name=name,
        attributes=[SimpleNamespace(name=c, order_index=i) for i, c in enumerate(columns)],
    )


def _action(kind: str, config: dict) -> SimpleNamespace:
    return SimpleNamespace(action_type=kind, action_config=config, enabled=True)


def _tables(table: SimpleNamespace) -> dict:
    return {str(table.id): table}


# --- табличные действия ----------------------------------------------------


def test_table_action_without_table_is_critical() -> None:
    findings = _check_action("правило «тест»", _action("table_write", {}), {})

    assert [f.level for f in findings] == ["critical"]
    assert "без таблицы" in findings[0].title


def test_table_action_pointing_at_deleted_table() -> None:
    findings = _check_action("правило «тест»", _action("table_find", {"table_id": str(uuid4())}), {})

    assert findings[0].level == "critical"
    assert "больше нет" in findings[0].title


def test_table_find_by_missing_column() -> None:
    table = _table("Заявки", ["phone", "name"])
    action = _action("table_find", {"table_id": str(table.id), "column": "email"})

    findings = _check_action("правило «тест»", action, _tables(table))

    assert findings[0].level == "critical"
    assert "email" in findings[0].title


def test_table_find_by_existing_column_is_clean() -> None:
    table = _table("Заявки", ["phone"])
    action = _action("table_find", {"table_id": str(table.id), "column": "phone"})

    assert _check_action("правило «тест»", action, _tables(table)) == []


def test_table_write_into_unknown_columns() -> None:
    table = _table("Заявки", ["phone"])
    action = _action("table_write", {"table_id": str(table.id), "values": {"phone": "1", "mail": "x"}})

    findings = _check_action("правило «тест»", action, _tables(table))

    assert findings[0].level == "critical"
    assert "mail" in findings[0].detail


def test_table_update_without_match_column() -> None:
    table = _table("Заявки", ["phone"])
    action = _action(
        "table_write", {"table_id": str(table.id), "mode": "upsert", "values": {"phone": "1"}}
    )

    findings = _check_action("правило «тест»", action, _tables(table))

    assert any("колонки сопоставления" in f.title for f in findings)


# --- прочие действия -------------------------------------------------------


def test_variable_without_name_is_warning() -> None:
    findings = _check_action("правило «тест»", _action("set_variable", {"value": "x"}), {})

    assert findings[0].level == "warning"


def test_augment_prompt_accepts_legacy_key() -> None:
    # На проводе instruction, но старые правила несут prompt — обе формы валидны.
    assert _check_action("правило «тест»", _action("augment_prompt", {"prompt": "будь краток"}), {}) == []


# --- рендер ----------------------------------------------------------------


def test_render_groups_by_severity() -> None:
    text = render_checks(
        [
            Finding("critical", "Таблица не выбрана", "упадёт"),
            Finding("warning", "Параметр без описания", "модель угадывает"),
        ]
    )

    assert "### Не работает" in text
    assert "### Работает плохо" in text
    assert text.index("### Не работает") < text.index("### Работает плохо")


def test_render_says_when_clean() -> None:
    text = render_checks([])

    assert "Проблем не нашлось" in text
    # Проверка про настройки, а не про качество ответов — это важно не спутать.
    assert "качеству ответов" in text
