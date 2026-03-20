from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.tenant_balance import (
    compute_charge_delta,
    estimate_embedding_cost_usd,
    resolve_run_cost_for_balance,
)


def test_resolve_run_cost_for_balance_prefers_logfire() -> None:
    run = SimpleNamespace(cost_usd=Decimal("1.2300000000"), cost_usd_logfire=Decimal("1.1000000000"))
    assert resolve_run_cost_for_balance(run) == Decimal("1.1000000000")


def test_resolve_run_cost_for_balance_falls_back_to_cost_usd() -> None:
    run = SimpleNamespace(cost_usd=Decimal("0.1200000000"), cost_usd_logfire=None)
    assert resolve_run_cost_for_balance(run) == Decimal("0.1200000000")


def test_compute_charge_delta_is_zero_for_same_amount() -> None:
    assert compute_charge_delta(Decimal("0.5000000000"), Decimal("0.5000000000")) == Decimal("0E-10")


def test_compute_charge_delta_returns_positive_or_negative_delta() -> None:
    assert compute_charge_delta(Decimal("1.0000000000"), Decimal("1.2500000000")) == Decimal("0.2500000000")
    assert compute_charge_delta(Decimal("1.2500000000"), Decimal("1.0000000000")) == Decimal("-0.2500000000")


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDb:
    def __init__(self, pricing):
        self._pricing = pricing

    async def execute(self, _stmt):
        return _FakeResult(self._pricing)


@pytest.mark.asyncio
async def test_estimate_embedding_cost_usd_uses_model_pricing_input() -> None:
    pricing = SimpleNamespace(input_usd=Decimal("2.00000000"))
    db = _FakeDb(pricing)
    amount = await estimate_embedding_cost_usd(db, model_name="text-embedding-3-small", input_tokens=200)
    assert amount == Decimal("0.0004000000")


@pytest.mark.asyncio
async def test_estimate_embedding_cost_usd_returns_none_without_pricing() -> None:
    db = _FakeDb(None)
    amount = await estimate_embedding_cost_usd(db, model_name="text-embedding-3-small", input_tokens=200)
    assert amount is None
