from __future__ import annotations

import json
import secrets
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.api.routers.webhooks_utils import mask_headers
from app.db.models.agent import Agent
from app.db.models.channel import AgentChannel, Channel
from app.db.session import get_db
from app.services.wappi import (
    ChannelProfileConfigError,
    ChannelProfileExternalError,
    ChannelProfileNotBoundError,
    ChannelProfileUnsupportedTypeError,
    configure_channel_webhook,
)
from app.services.wappi.webhooks import (
    extract_phone_auth_state,
    extract_phone_webhook_auth_secret,
    handle_wappi_channel_messages,
)

logger = structlog.get_logger()
wappi_webhook_logger = structlog.get_logger("webhooks.wappi")
_WAPPI_PLATFORM_WEBHOOK_LOGGERS = {
    "telegram_phone": structlog.get_logger("webhooks.wappi.telegram"),
    "whatsapp": structlog.get_logger("webhooks.wappi.whatsapp"),
    "max": structlog.get_logger("webhooks.wappi.max"),
}

router = APIRouter()

_PHONE_CHANNEL_TYPES = {"telegram_phone", "whatsapp", "max"}


def _build_phone_channel_webhook_url(channel_id: UUID) -> str | None:
    settings = get_settings()
    base_url = (settings.public_base_url or "").rstrip("/")
    if not base_url:
        return None
    endpoint = f"{settings.api_prefix}/webhooks/channels/phone/{channel_id}"
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{base_url}{endpoint}"


@router.post("/webhooks/channels/phone/{channel_id}")
async def phone_channel_webhook(
    channel_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    stmt = select(Channel).where(
        Channel.id == channel_id,
        Channel.is_deleted.is_(False),
    )
    result = await db.execute(stmt)
    channel = result.scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    if channel.type not in _PHONE_CHANNEL_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Channel is not phone type")

    expected_secret = str(channel.wappi_webhook_secret or "").strip()
    if expected_secret:
        provided_secret = extract_phone_webhook_auth_secret(request)
        if not provided_secret or not secrets.compare_digest(provided_secret, expected_secret):
            wappi_webhook_logger.warning(
                "phone_channel_webhook_secret_invalid",
                channel_id=str(channel.id),
                channel_type=channel.type,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret",
            )

    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    parsed_json: dict[str, Any] | list[Any] | None = None
    if raw_body:
        try:
            parsed_json = json.loads(raw_body)
        except Exception:
            parsed_json = None

    payload_for_state = parsed_json if isinstance(parsed_json, (dict, list)) else None
    auth_state = (
        extract_phone_auth_state(
            payload_for_state,
            expected_profile_id=channel.wappi_profile_id,
        )
        if payload_for_state is not None
        else None
    )

    previous_auth_state = bool(channel.phone_is_authorized)
    changed_auth_state = False
    webhook_reconfigured = False
    if auth_state is not None and previous_auth_state != auth_state:
        channel.phone_is_authorized = auth_state
        if auth_state:
            profile_id = (channel.wappi_profile_id or "").strip()
            webhook_url = _build_phone_channel_webhook_url(channel.id)
            if not profile_id:
                wappi_webhook_logger.warning(
                    "phone_channel_webhook_reconfigure_skipped_no_profile",
                    channel_id=str(channel.id),
                    channel_type=channel.type,
                )
            elif not webhook_url:
                wappi_webhook_logger.warning(
                    "phone_channel_webhook_reconfigure_skipped_no_public_base_url",
                    channel_id=str(channel.id),
                    channel_type=channel.type,
                )
            else:
                try:
                    await configure_channel_webhook(
                        db=db,
                        channel=channel,
                        webhook_url=webhook_url,
                        profile_id=profile_id,
                        rotate_secret=False,
                    )
                    webhook_reconfigured = True
                except (
                    ChannelProfileConfigError,
                    ChannelProfileExternalError,
                    ChannelProfileNotBoundError,
                    ChannelProfileUnsupportedTypeError,
                ) as exc:
                    wappi_webhook_logger.warning(
                        "phone_channel_webhook_reconfigure_failed",
                        channel_id=str(channel.id),
                        channel_type=channel.type,
                        profile_id=profile_id,
                        error=str(exc),
                    )
        await db.commit()
        changed_auth_state = True

    log_payload: dict[str, Any] = {
        "channel_id": str(channel.id),
        "channel_type": channel.type,
        "method": request.method,
        "path": str(request.url.path),
        "query_params": dict(request.query_params),
        "headers": mask_headers(dict(request.headers)),
        "body_raw": raw_text,
        "body_json": parsed_json,
        "client_ip": request.client.host if request.client else "unknown",
        "detected_auth_state": auth_state,
        "previous_auth_state": previous_auth_state,
        "changed_auth_state": changed_auth_state,
        "webhook_reconfigured_after_auth": webhook_reconfigured,
    }
    wappi_webhook_logger.info("phone_channel_webhook_incoming", **log_payload)
    platform_wappi_logger = _WAPPI_PLATFORM_WEBHOOK_LOGGERS.get(channel.type)
    if platform_wappi_logger is not None:
        platform_wappi_logger.info("phone_channel_webhook_incoming", **log_payload)
    logger.info("phone_channel_webhook_received", **log_payload)

    if isinstance(parsed_json, dict):
        stmt_agent = (
            select(AgentChannel.agent_id, Agent)
            .join(Agent, Agent.id == AgentChannel.agent_id)
            .where(
                AgentChannel.channel_id == channel_id,
                Agent.is_deleted.is_(False),
            )
        )
        agent_row = (await db.execute(stmt_agent)).first()
        if agent_row is not None:
            bound_agent_id, bound_agent = agent_row
            await handle_wappi_channel_messages(
                db,
                channel=channel,
                agent_id=bound_agent_id,
                agent=bound_agent,
                parsed_json=parsed_json,
            )

    return {"ok": True}
