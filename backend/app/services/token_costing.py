from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.model_pricing import ModelPricing

logger = structlog.get_logger(__name__)

TOKENS_IN_MILLION = Decimal("1000000")
COST_QUANT = Decimal("0.0000000001")


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _quantize_cost(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(COST_QUANT, rounding=ROUND_HALF_UP)


def _sum_costs(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return _quantize_cost(sum(values))


def _normalize_model_reference(model_reference: str | None) -> tuple[str, list[str]]:
    if not model_reference:
        return "openai", []

    normalized = model_reference.strip()
    if ":" in normalized:
        provider, model_name = normalized.split(":", 1)
    else:
        provider, model_name = "openai", normalized

    candidates: list[str] = [model_name]

    # gpt-4o-2024-08-06 -> gpt-4o
    m = re.match(r"^(.*)-\d{4}-\d{2}-\d{2}$", model_name)
    if m:
        base_name = m.group(1)
        if base_name and base_name not in candidates:
            candidates.append(base_name)

    return provider, candidates


async def _load_pricing(
    db: AsyncSession,
    provider: str,
    model_candidates: list[str],
    cache: dict[str, ModelPricing | None],
) -> ModelPricing | None:
    for model_name in model_candidates:
        cache_key = f"{provider}:{model_name}"
        if cache_key in cache:
            cached = cache[cache_key]
            if cached is not None:
                return cached
            continue

        stmt = (
            select(ModelPricing)
            .where(
                ModelPricing.provider == provider,
                ModelPricing.model_name == model_name,
                ModelPricing.is_active.is_(True),
            )
            .limit(1)
        )
        pricing = (await db.execute(stmt)).scalar_one_or_none()
        cache[cache_key] = pricing
        if pricing is not None:
            return pricing

    return None


def _resolve_input_tokens(step: dict[str, Any]) -> tuple[int, int, int]:
    prompt_tokens = int(step.get("prompt_tokens") or 0)
    completion_tokens = int(step.get("completion_tokens") or 0)

    cached_tokens_raw = step.get("input_cached_tokens")
    non_cached_tokens_raw = step.get("input_non_cached_tokens")

    cached_tokens = int(cached_tokens_raw) if cached_tokens_raw is not None else None
    non_cached_tokens = int(non_cached_tokens_raw) if non_cached_tokens_raw is not None else None

    if non_cached_tokens is None:
        if cached_tokens is not None:
            non_cached_tokens = max(prompt_tokens - cached_tokens, 0)
        else:
            non_cached_tokens = prompt_tokens

    if cached_tokens is None:
        cached_tokens = max(prompt_tokens - non_cached_tokens, 0)

    cached_tokens = max(min(cached_tokens, prompt_tokens), 0)
    non_cached_tokens = max(min(non_cached_tokens, prompt_tokens), 0)

    if cached_tokens + non_cached_tokens < prompt_tokens:
        non_cached_tokens += prompt_tokens - (cached_tokens + non_cached_tokens)

    return non_cached_tokens, cached_tokens, completion_tokens


def _calculate_currency_cost(
    *,
    non_cached_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    input_price: Decimal | None,
    cached_input_price: Decimal | None,
    output_price: Decimal | None,
) -> Decimal | None:
    if non_cached_tokens > 0 and input_price is None:
        return None
    if cached_tokens > 0 and cached_input_price is None and input_price is None:
        return None
    if output_tokens > 0 and output_price is None:
        return None

    resolved_cached_price = cached_input_price if cached_input_price is not None else input_price
    if resolved_cached_price is None and cached_tokens > 0:
        return None

    total = Decimal("0")
    if non_cached_tokens > 0 and input_price is not None:
        total += Decimal(non_cached_tokens) * input_price
    if cached_tokens > 0 and resolved_cached_price is not None:
        total += Decimal(cached_tokens) * resolved_cached_price
    if output_tokens > 0 and output_price is not None:
        total += Decimal(output_tokens) * output_price

    return _quantize_cost(total / TOKENS_IN_MILLION)


def _calculate_step_cost(
    step: dict[str, Any],
    pricing: ModelPricing | None,
) -> tuple[Decimal | None, Decimal | None]:
    if pricing is None:
        return None, None

    non_cached_tokens, cached_tokens, output_tokens = _resolve_input_tokens(step)

    usd_cost = _calculate_currency_cost(
        non_cached_tokens=non_cached_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        input_price=_to_decimal(pricing.input_usd),
        cached_input_price=_to_decimal(pricing.cached_input_usd),
        output_price=_to_decimal(pricing.output_usd),
    )
    rub_cost = _calculate_currency_cost(
        non_cached_tokens=non_cached_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        input_price=_to_decimal(pricing.input_rub),
        cached_input_price=_to_decimal(pricing.cached_input_rub),
        output_price=_to_decimal(pricing.output_rub),
    )
    return usd_cost, rub_cost


async def apply_fallback_costs(
    db: AsyncSession,
    *,
    token_usage_steps: list[dict[str, Any]] | None,
) -> tuple[Decimal | None, Decimal | None]:
    if not token_usage_steps:
        return None, None

    pricing_cache: dict[str, ModelPricing | None] = {}
    missing_pricing_models: set[str] = set()

    for step in token_usage_steps:
        if not isinstance(step, dict):
            continue

        model_reference = step.get("model_name")
        provider, model_candidates = _normalize_model_reference(model_reference)
        pricing = await _load_pricing(db, provider, model_candidates, pricing_cache)
        if pricing is None:
            if model_reference:
                missing_pricing_models.add(str(model_reference))
            step["cost_usd"] = None
            step["cost_rub"] = None
            continue

        usd_cost, rub_cost = _calculate_step_cost(step, pricing)
        step["cost_usd"] = usd_cost
        step["cost_rub"] = rub_cost

    if missing_pricing_models:
        logger.info("model_pricing_missing", models=sorted(missing_pricing_models))

    total_usd = _sum_costs([value for value in [step.get("cost_usd") for step in token_usage_steps] if isinstance(value, Decimal)])
    total_rub = _sum_costs([value for value in [step.get("cost_rub") for step in token_usage_steps] if isinstance(value, Decimal)])
    return total_usd, total_rub
