from __future__ import annotations

from decimal import Decimal

from app.services.sqns.visit_commodity_extraction import (
    extract_commodity_refs_from_payment_payload,
    extract_commodity_refs_from_visit_payload,
)


def test_visit_single_commodity_nested() -> None:
    raw = {"visit": {"commodity": {"id": 42, "title": "Паста"}}}
    refs = extract_commodity_refs_from_visit_payload(raw)
    assert len(refs) == 1
    assert refs[0].commodity_external_id == 42
    assert refs[0].title == "Паста"


def test_visit_commodities_array() -> None:
    raw = {
        "commodities": [
            {"commodityId": 1, "title": "A", "quantity": 2, "amount": "100.5"},
            {"commodity_id": 2, "name": "B"},
        ]
    }
    refs = extract_commodity_refs_from_visit_payload(raw)
    assert len(refs) == 2
    assert refs[0].commodity_external_id == 1
    assert refs[0].quantity == Decimal("2")
    assert refs[0].amount == Decimal("100.5")
    assert refs[1].commodity_external_id == 2
    assert refs[1].title == "B"


def test_visit_items_filtered_by_type() -> None:
    raw = {
        "items": [
            {"type": "service", "id": 99, "name": "Услуга"},
            {"type": "commodity", "id": 7, "name": "Товар"},
        ]
    }
    refs = extract_commodity_refs_from_visit_payload(raw)
    assert len(refs) == 1
    assert refs[0].commodity_external_id == 7


def test_payment_wraps_visit_shape() -> None:
    raw = {
        "visitId": 500,
        "data": {
            "positions": [
                {"commodityId": 3, "title": "X", "quantity": 1},
            ]
        },
    }
    refs = extract_commodity_refs_from_payment_payload(raw)
    assert len(refs) == 1
    assert refs[0].commodity_external_id == 3


def test_empty_visit() -> None:
    assert extract_commodity_refs_from_visit_payload({}) == []
    assert extract_commodity_refs_from_visit_payload(None) == []
