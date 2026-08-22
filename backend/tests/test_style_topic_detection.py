"""Определение темы разговора — без привязки к домену и именам инструментов.

Навык объявляет ключи привязки (внешние id услуги/товара/тарифа), рантайм ищет
их в результатах ЛЮБЫХ инструментов сессии. Так механизм работает и для клиники
на SQNS, и для агента из другой сферы с собственными инструментами.
"""

from app.services.runtime.skill_layer import _collect_id_like_values


def test_finds_ids_in_nested_payload():
    payload = {
        "resolved": {"service_external_id": "1068"},
        "services": [{"external_id": "524"}, {"external_id": "980"}],
    }
    assert _collect_id_like_values(payload) == {"1068", "524", "980"}


def test_works_for_other_business_domains():
    """Автосалон: свой инструмент, свои поля — механизм тот же."""
    payload = {"vehicles": [{"model_id": "kia-rio", "price": 1850000}]}
    assert "kia-rio" in _collect_id_like_values(payload)


def test_ignores_non_id_fields():
    """Цена и текст не должны попадать в кандидаты — иначе тема определится
    случайным совпадением числа."""
    payload = {"price": "524", "title": "1068", "comment": "980"}
    assert _collect_id_like_values(payload) == set()


def test_ignores_booleans_and_none():
    payload = {"service_id": None, "is_id_valid": True, "code": "A1"}
    assert _collect_id_like_values(payload) == {"A1"}


def test_handles_flat_and_empty():
    assert _collect_id_like_values({}) == set()
    assert _collect_id_like_values([]) == set()
    assert _collect_id_like_values({"id": 42}) == {"42"}


def test_list_of_scalars_inherits_field_name():
    payload = {"service_ids": ["1", "2"], "names": ["Анна", "Мария"]}
    assert _collect_id_like_values(payload) == {"1", "2"}
