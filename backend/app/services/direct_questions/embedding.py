from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.directory.service import create_embedding


async def create_direct_question_embedding(
    text: str,
    *,
    db: AsyncSession | None = None,
    tenant_id: UUID | None = None,
    charge_source_type: str | None = None,
    charge_source_id: str | None = None,
    charge_metadata: dict[str, Any] | None = None,
    openai_api_key: str | None,
) -> list[float] | None:
    return await create_embedding(
        text,
        openai_api_key=openai_api_key,
        db=db,
        tenant_id=tenant_id,
        charge_source_type=charge_source_type,
        charge_source_id=charge_source_id,
        charge_metadata=charge_metadata,
    )
