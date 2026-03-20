from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.tenant_balance import apply_embedding_balance_charge
from app.services.runtime.model_resolver import resolve_openai_client

logger = structlog.get_logger(__name__)


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
    if not openai_api_key:
        return None

    settings = get_settings()
    try:
        client = resolve_openai_client(openai_api_key=openai_api_key)
        response = await asyncio.wait_for(
            client.embeddings.create(input=text, model=settings.embedding_model),
            timeout=max(settings.direct_questions_embedding_timeout_ms, 1) / 1000.0,
        )
        embedding = response.data[0].embedding
        if db is not None and tenant_id is not None and charge_source_type:
            usage = getattr(response, "usage", None)
            total_tokens = getattr(usage, "total_tokens", None)
            if total_tokens is None:
                total_tokens = getattr(usage, "prompt_tokens", None)
            if isinstance(total_tokens, int) and total_tokens > 0:
                metadata = {
                    "model": settings.embedding_model,
                    "input_tokens": total_tokens,
                    **(charge_metadata or {}),
                }
                try:
                    await apply_embedding_balance_charge(
                        db,
                        tenant_id=tenant_id,
                        model_name=settings.embedding_model,
                        input_tokens=total_tokens,
                        source_type=charge_source_type,
                        source_id=charge_source_id or str(uuid4()),
                        metadata=metadata,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("direct_question_embedding_balance_charge_failed", error=str(exc))
        return embedding
    except TimeoutError:
        logger.warning("direct_question_embedding_timeout")
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("direct_question_embedding_failed", error=str(exc))
        return None
