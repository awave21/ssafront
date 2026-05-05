"""Public widget endpoints — no auth cookie required, CORS: any origin."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.api_key import ApiKey
from app.db.models.channel import Channel
from app.db.session import get_db
from app.schemas.channel import WidgetSettings
from app.services.api_keys import hash_api_key

from fastapi import Depends

router = APIRouter()


class WidgetConfigResponse(BaseModel):
    agent_name: str
    settings: WidgetSettings
    allowed_origins: list[str]


@router.get("/config", response_model=WidgetConfigResponse, summary="Публичная конфигурация виджета")
async def get_widget_config(
    request: Request,
    key: str = Query(..., description="API key виджета"),
    db: AsyncSession = Depends(get_db),
) -> WidgetConfigResponse:
    settings = get_settings()
    key_hash = hash_api_key(key, settings.api_key_pepper)

    stmt = (
        select(ApiKey)
        .where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    )
    result = await db.execute(stmt)
    api_key_obj = result.scalar_one_or_none()

    if api_key_obj is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    if api_key_obj.agent_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Key not bound to agent")

    # Load channel settings via widget_api_key_id
    chan_stmt = select(Channel).where(
        Channel.widget_api_key_id == api_key_obj.id,
        Channel.is_deleted.is_(False),
    )
    chan_result = await db.execute(chan_stmt)
    channel = chan_result.scalar_one_or_none()

    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget channel not found")

    allowed_origins: list[str] = channel.widget_allowed_origins or []

    # Check Origin header against allowed list
    if allowed_origins:
        origin = request.headers.get("origin") or request.headers.get("referer", "")
        origin_host = _extract_host(origin)
        if origin_host and origin_host not in allowed_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin not allowed",
            )

    # Load agent name
    from app.db.models.agent import Agent
    agent_stmt = select(Agent.name).where(Agent.id == api_key_obj.agent_id)
    agent_result = await db.execute(agent_stmt)
    agent_name = agent_result.scalar_one_or_none() or "Ассистент"

    raw_settings: dict = channel.widget_settings or {}
    widget_settings = WidgetSettings(**raw_settings)

    return WidgetConfigResponse(
        agent_name=agent_name,
        settings=widget_settings,
        allowed_origins=allowed_origins,
    )


def _extract_host(origin: str) -> str:
    """Extract hostname from origin or referer URL."""
    import urllib.parse
    try:
        parsed = urllib.parse.urlparse(origin)
        return parsed.hostname or ""
    except Exception:
        return ""
