from __future__ import annotations

from types import SimpleNamespace

from app.services.user_table.runtime import coerce_value


def _attr(kind: str, **type_config):
    return SimpleNamespace(name="col", attribute_type=kind, type_config=type_config)


# Шаблоны {{...}} всегда отдают строку, поэтому колонки-числа и флаги должны
# приводиться, иначе validate_record_data отвергнет запись.


def test_integer_from_string() -> None:
    assert coerce_value(_attr("integer"), " 42 ") == 42
    assert isinstance(coerce_value(_attr("integer"), "42"), int)


def test_float_accepts_comma_decimal() -> None:
    # Пользователи и CSV из Excel пишут дробные через запятую.
    assert coerce_value(_attr("float"), "3,5") == 3.5
    assert coerce_value(_attr("float"), "3.5") == 3.5


def test_boolean_from_common_tokens() -> None:
    for truthy in ("true", "1", "да", "Yes", " ON "):
        assert coerce_value(_attr("boolean"), truthy) is True
    for falsy in ("false", "0", "нет", "No", ""):
        assert coerce_value(_attr("boolean"), falsy) is False


def test_boolean_passes_through_real_bool() -> None:
    assert coerce_value(_attr("boolean"), True) is True
    assert coerce_value(_attr("boolean"), False) is False


def test_text_array_splits_comma_separated_string() -> None:
    assert coerce_value(_attr("text_array"), "a, b ,c") == ["a", "b", "c"]
    assert coerce_value(_attr("text_array"), ["a", "b"]) == ["a", "b"]


def test_unparsable_value_is_returned_as_is() -> None:
    # Не глотаем ошибку: пусть на значении ругается валидатор с понятным
    # сообщением, а не мы молча подставим 0.
    assert coerce_value(_attr("integer"), "не число") == "не число"
    assert coerce_value(_attr("float"), "abc") == "abc"
    assert coerce_value(_attr("boolean"), "может быть") == "может быть"


def test_text_is_stringified() -> None:
    assert coerce_value(_attr("text"), 42) == "42"


def test_missing_attribute_or_none_passes_through() -> None:
    assert coerce_value(None, "что угодно") == "что угодно"
    assert coerce_value(_attr("integer"), None) is None
