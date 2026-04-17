from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_404, require_scope
from app.db.models.model_pricing import ModelPricing
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.model_pricing import (
    ActiveModelGroup,
    ActiveModelOption,
    ModelPricingCreate,
    ModelPricingRead,
    ModelPricingUpdate,
)
from app.services.audit import write_audit

router = APIRouter()

MODEL_PRESETS: dict[str, dict[str, str]] = {
    "openai:gpt-5.2": {"group": "GPT-5 (Рекомендуемые - 2026)", "label": "GPT-5.2 (Лучшая для кодинга и агентов)"},
    "openai:gpt-5.2-pro": {"group": "GPT-5 (Рекомендуемые - 2026)", "label": "GPT-5.2 Pro (Умнее и точнее)"},
    "openai:gpt-5-mini": {"group": "GPT-5 (Рекомендуемые - 2026)", "label": "GPT-5 Mini (Быстрая, экономная)"},
    "openai:gpt-5-nano": {"group": "GPT-5 (Рекомендуемые - 2026)", "label": "GPT-5 Nano (Самая быстрая)"},
    "openai:gpt-5.1": {"group": "GPT-5 (Рекомендуемые - 2026)", "label": "GPT-5.1 (Предыдущее поколение)"},
    "openai:gpt-5": {"group": "GPT-5 (Рекомендуемые - 2026)", "label": "GPT-5 (Стабильная)"},
    "openai:gpt-4.1": {"group": "GPT-4.1 (Не-reasoning модели)", "label": "GPT-4.1 (Умная, без рассуждений)"},
    "openai:gpt-4.1-mini": {"group": "GPT-4.1 (Не-reasoning модели)", "label": "GPT-4.1 Mini (Быстрая)"},
    "openai:gpt-4.1-nano": {"group": "GPT-4.1 (Не-reasoning модели)", "label": "GPT-4.1 Nano (Экономная)"},
    "openai:gpt-4o": {"group": "GPT-4o (Легаси)", "label": "GPT-4o (Мультимодальная)"},
    "openai:gpt-4o-mini": {"group": "GPT-4o (Легаси)", "label": "GPT-4o Mini (Быстрая, дешевая)"},
    "openai:o3": {"group": "Reasoning модели", "label": "o3 (Сложные задачи)"},
    "openai:o3-pro": {"group": "Reasoning модели", "label": "o3 Pro (Больше вычислений)"},
    "openai:o4-mini": {"group": "Reasoning модели", "label": "o4 Mini (Быстрые рассуждения)"},
    "anthropic:claude-sonnet-4-5": {"group": "Claude (Anthropic)", "label": "Claude Sonnet 4.5"},
    "anthropic:claude-3-5-sonnet-20241022": {"group": "Claude (Anthropic)", "label": "Claude 3.5 Sonnet"},
    "anthropic:claude-3-5-haiku-20241022": {"group": "Claude (Anthropic)", "label": "Claude 3.5 Haiku"},
}

GROUP_ORDER = {
    "GPT-5 (Рекомендуемые - 2026)": 0,
    "GPT-4.1 (Не-reasoning модели)": 1,
    "GPT-4o (Легаси)": 2,
    "Reasoning модели": 3,
    "Claude (Anthropic)": 4,
    "Другие": 99,
}
MODEL_ORDER = {value: idx for idx, value in enumerate(MODEL_PRESETS.keys())}


@router.post("", response_model=ModelPricingRead, status_code=status.HTTP_201_CREATED)
async def create_model_pricing(
    payload: ModelPricingCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("model_pricing:write")),
) -> ModelPricingRead:
    row = ModelPricing(**payload.model_dump())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model pricing already exists for provider/model",
        ) from exc
    await db.refresh(row)
    await write_audit(db, user, "model_pricing.create", "model_pricing", str(row.id))
    return ModelPricingRead.model_validate(row)


@router.get("", response_model=list[ModelPricingRead])
async def list_model_pricing(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("model_pricing:read")),
) -> list[ModelPricingRead]:
    stmt = select(ModelPricing)
    if not include_inactive:
        stmt = stmt.where(ModelPricing.is_active.is_(True))
    stmt = stmt.order_by(ModelPricing.provider.asc(), ModelPricing.model_name.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return [ModelPricingRead.model_validate(item) for item in rows]


@router.get("/active-models", response_model=list[ActiveModelGroup])
async def list_active_models_for_frontend(
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> list[ActiveModelGroup]:
    stmt = (
        select(ModelPricing)
        .where(ModelPricing.is_active.is_(True))
        .order_by(ModelPricing.provider.asc(), ModelPricing.model_name.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    grouped: dict[str, list[ActiveModelOption]] = defaultdict(list)
    for row in rows:
        value = f"{row.provider}:{row.model_name}"
        preset = MODEL_PRESETS.get(value)
        group_name = preset["group"] if preset else "Другие"
        label = row.display_name or (preset["label"] if preset else row.model_name)
        grouped[group_name].append(
            ActiveModelOption(
                value=value,
                provider=row.provider,
                model_name=row.model_name,
                label=label,
            )
        )

    groups: list[ActiveModelGroup] = []
    for group_name, options in grouped.items():
        options.sort(key=lambda x: (MODEL_ORDER.get(x.value, 9999), x.label.lower()))
        groups.append(ActiveModelGroup(group=group_name, options=options))

    groups.sort(key=lambda g: GROUP_ORDER.get(g.group, 999))
    return groups


@router.get("/{pricing_id}", response_model=ModelPricingRead)
async def get_model_pricing(
    pricing_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("model_pricing:read")),
) -> ModelPricingRead:
    row = await get_or_404(db, ModelPricing, id=pricing_id, label="Model pricing")
    return ModelPricingRead.model_validate(row)


@router.put("/{pricing_id}", response_model=ModelPricingRead)
async def update_model_pricing(
    pricing_id: UUID,
    payload: ModelPricingUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("model_pricing:write")),
) -> ModelPricingRead:
    row = await get_or_404(db, ModelPricing, id=pricing_id, label="Model pricing")

    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, key, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Model pricing already exists for provider/model",
        ) from exc
    await db.refresh(row)
    await write_audit(db, user, "model_pricing.update", "model_pricing", str(row.id))
    return ModelPricingRead.model_validate(row)


@router.delete("/{pricing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_pricing(
    pricing_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("model_pricing:write")),
) -> None:
    row = await get_or_404(db, ModelPricing, id=pricing_id, label="Model pricing")

    await db.delete(row)
    await db.commit()
    await write_audit(db, user, "model_pricing.delete", "model_pricing", str(pricing_id))
