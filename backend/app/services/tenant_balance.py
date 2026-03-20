from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.model_pricing import ModelPricing
from app.db.models.run import Run
from app.db.models.tenant_balance import TenantBalance
from app.db.models.tenant_balance_charge import TenantBalanceCharge

_COST_QUANT = Decimal("0.0000000001")
_TOKENS_IN_MILLION = Decimal("1000000")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_COST_QUANT, rounding=ROUND_HALF_UP)


def _to_decimal(value: Decimal | int | float | str | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return _quantize(value)
    try:
        return _quantize(Decimal(str(value)))
    except Exception:
        return None


def resolve_run_cost_for_balance(run: Run) -> Decimal | None:
    if run.cost_usd_logfire is not None:
        return _to_decimal(run.cost_usd_logfire)
    return _to_decimal(run.cost_usd)


def compute_charge_delta(previous_amount: Decimal, next_amount: Decimal) -> Decimal:
    return _quantize(next_amount - previous_amount)


async def get_tenant_balance(db: AsyncSession, *, tenant_id: UUID) -> TenantBalance | None:
    stmt = select(TenantBalance).where(TenantBalance.tenant_id == tenant_id).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def ensure_tenant_balance_for_update(db: AsyncSession, *, tenant_id: UUID) -> TenantBalance:
    stmt = (
        select(TenantBalance)
        .where(TenantBalance.tenant_id == tenant_id)
        .with_for_update()
        .limit(1)
    )
    balance = (await db.execute(stmt)).scalar_one_or_none()
    if balance is not None:
        return balance
    balance = TenantBalance(
        tenant_id=tenant_id,
        initial_balance_usd=Decimal("0"),
        spent_usd=Decimal("0"),
    )
    db.add(balance)
    await db.flush()
    return balance


async def set_tenant_initial_balance(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    initial_balance_usd: Decimal,
) -> TenantBalance:
    amount = _to_decimal(initial_balance_usd)
    if amount is None or amount < 0:
        raise ValueError("initial_balance_usd must be a non-negative decimal")
    balance = await ensure_tenant_balance_for_update(db, tenant_id=tenant_id)
    balance.initial_balance_usd = amount
    await db.flush()
    return balance


async def apply_balance_charge(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    amount_usd: Decimal,
    source_type: str,
    source_id: str,
    metadata: dict | None = None,
) -> bool:
    normalized_amount = _to_decimal(amount_usd)
    if normalized_amount is None:
        return False
    if normalized_amount < 0:
        raise ValueError("amount_usd must be non-negative")

    balance = await ensure_tenant_balance_for_update(db, tenant_id=tenant_id)
    charge_stmt = (
        select(TenantBalanceCharge)
        .where(
            TenantBalanceCharge.tenant_id == tenant_id,
            TenantBalanceCharge.source_type == source_type,
            TenantBalanceCharge.source_id == source_id,
        )
        .with_for_update()
        .limit(1)
    )
    charge = (await db.execute(charge_stmt)).scalar_one_or_none()

    delta = normalized_amount
    if charge is None:
        charge = TenantBalanceCharge(
            tenant_id=tenant_id,
            source_type=source_type,
            source_id=source_id,
            amount_usd=normalized_amount,
            metadata_json=metadata,
        )
        db.add(charge)
    else:
        previous_amount = _to_decimal(charge.amount_usd) or Decimal("0")
        delta = compute_charge_delta(previous_amount, normalized_amount)
        if delta == 0:
            if metadata is not None:
                charge.metadata_json = metadata
                await db.flush()
            return False
        charge.amount_usd = normalized_amount
        if metadata is not None:
            charge.metadata_json = metadata

    current_spent = _to_decimal(balance.spent_usd) or Decimal("0")
    balance.spent_usd = _quantize(current_spent + delta)
    await db.flush()
    return True


async def sync_run_balance_charge(db: AsyncSession, *, run: Run) -> bool:
    amount = resolve_run_cost_for_balance(run)
    if amount is None:
        return False
    return await apply_balance_charge(
        db,
        tenant_id=run.tenant_id,
        amount_usd=amount,
        source_type="run_cost_usd",
        source_id=str(run.id),
        metadata={"trace_id": run.trace_id, "status": run.logfire_reconcile_status},
    )


async def estimate_embedding_cost_usd(
    db: AsyncSession,
    *,
    model_name: str,
    input_tokens: int,
) -> Decimal | None:
    if input_tokens <= 0:
        return Decimal("0")
    stmt = (
        select(ModelPricing)
        .where(
            ModelPricing.provider == "openai",
            ModelPricing.model_name == model_name,
            ModelPricing.is_active.is_(True),
        )
        .limit(1)
    )
    pricing = (await db.execute(stmt)).scalar_one_or_none()
    if pricing is None or pricing.input_usd is None:
        return None
    amount = (Decimal(input_tokens) * Decimal(pricing.input_usd)) / _TOKENS_IN_MILLION
    return _quantize(amount)


async def apply_embedding_balance_charge(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    model_name: str,
    input_tokens: int,
    source_type: str,
    source_id: str | None = None,
    metadata: dict | None = None,
) -> bool:
    amount = await estimate_embedding_cost_usd(db, model_name=model_name, input_tokens=input_tokens)
    if amount is None:
        return False
    resolved_source_id = source_id or str(uuid4())
    return await apply_balance_charge(
        db,
        tenant_id=tenant_id,
        amount_usd=amount,
        source_type=source_type,
        source_id=resolved_source_id,
        metadata=metadata,
    )
