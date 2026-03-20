from __future__ import annotations

from datetime import datetime
import secrets
import structlog
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_scope
from app.core.config import get_settings
from app.db.models.channel import AgentChannel, Channel
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.channel import (
    ChannelAuthQrRead,
    ChannelConnectionPayload,
    ChannelDisconnectPayload,
    ChannelRead,
)
from app.services.audit import write_audit
from app.services.telegram import TelegramWebhookError, set_telegram_webhook
from app.services.wappi import (
    ChannelProfileConfigError,
    ChannelProfileExternalError,
    ChannelProfileNotBoundError,
    ChannelProfileUnsupportedTypeError,
    bind_profile_to_channel,
    request_channel_auth_qr,
    unbind_profile_from_channel,
)

from app.api.routers.agents.deps import get_agent_or_404

router = APIRouter()
webhook_logger = structlog.get_logger("webhooks")
wappi_webhook_logger = structlog.get_logger("webhooks.wappi")

AVAILABLE_CHANNEL_TYPES = ["Telegram_Bot", "Telegram_Phone", "Whatsapp_Phone", "Max_Phone"]
CHANNEL_TYPE_MAP = {
    "Telegram_Bot": "telegram",
    "Telegram_Phone": "telegram_phone",
    "Whatsapp_Phone": "whatsapp",
    "Max_Phone": "max",
}
WAPPI_PHONE_CHANNEL_TYPES = {"telegram_phone", "whatsapp", "max"}


def _generate_webhook_token() -> str:
    return secrets.token_urlsafe(32)


def _generate_webhook_secret() -> str:
    return secrets.token_urlsafe(32)


def _build_telegram_webhook_endpoint(token: str) -> str:
    return f"{get_settings().api_prefix}/webhooks/telegram/{token}"


def _build_phone_channel_webhook_endpoint(channel_id: UUID) -> str:
    return f"{get_settings().api_prefix}/webhooks/channels/phone/{channel_id}"


def _build_public_webhook_url(endpoint: str) -> str:
    base_url = (get_settings().public_base_url or "").rstrip("/")
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PUBLIC_BASE_URL is not configured",
        )
    if not endpoint.startswith("/"):
        endpoint = f"/{endpoint}"
    return f"{base_url}{endpoint}"


def _ensure_telegram_webhook(channel: Channel) -> None:
    token = channel.telegram_webhook_token or _generate_webhook_token()
    if not channel.telegram_webhook_token:
        channel.telegram_webhook_token = token
    channel.telegram_webhook_endpoint = _build_telegram_webhook_endpoint(token)
    if not channel.telegram_webhook_secret:
        channel.telegram_webhook_secret = _generate_webhook_secret()


def _log_telegram_webhook_connected(*, agent_id: UUID, channel: Channel, action: str) -> None:
    webhook_logger.info(
        "telegram_webhook_connected",
        agent_id=str(agent_id),
        channel_id=str(channel.id),
        action=action,
        webhook_enabled=bool(channel.telegram_webhook_enabled),
        webhook_token_present=bool(channel.telegram_webhook_token),
    )


def _resolve_channel_type(channel_type: str) -> str:
    resolved = CHANNEL_TYPE_MAP.get(channel_type)
    if resolved is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported channel type")
    return resolved


def _build_wappi_profile_name(agent_name: str, channel_type: str, channel_id: UUID) -> str:
    normalized_agent = " ".join((agent_name or "").strip().split()) or "Agent"
    type_label_map = {
        "telegram_phone": "TelegramPhone",
        "whatsapp": "WhatsAppPhone",
        "max": "MaxPhone",
    }
    type_label = type_label_map.get(channel_type, "Phone")
    return f"{normalized_agent} {type_label} {str(channel_id)[:8]}"


async def _get_channel_for_agent_by_type_or_404(
    db: AsyncSession,
    agent_id: UUID,
    channel_type: str,
) -> tuple[Channel, AgentChannel]:
    stmt = (
        select(Channel, AgentChannel)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.type == channel_type,
            Channel.is_deleted.is_(False),
        )
        .order_by(Channel.created_at.desc())
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return row


@router.get(
    "/{agent_id}/channels",
    response_model=list[str],
    summary="Список доступных каналов",
    response_description="Доступные типы каналов для подключения",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": ["Telegram_Bot", "Telegram_Phone", "Whatsapp_Phone", "Max_Phone"],
                }
            }
        }
    },
)
async def list_available_channels(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[str]:
    await get_agent_or_404(agent_id, db, user)
    return AVAILABLE_CHANNEL_TYPES


@router.get(
    "/{agent_id}/channels/active",
    response_model=list[ChannelRead],
    summary="Активные каналы агента",
    response_description="Подключенные каналы с токеном и webhook-данными",
    responses={
        200: {
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "2b96bfe0-2f1e-4f50-9b9e-5a2b4d7c18b2",
                            "type": "telegram",
                            "telegram_bot_token": "123456:ABCDEF",
                            "telegram_webhook_enabled": True,
                            "telegram_webhook_endpoint": "/api/v1/webhooks/telegram/abc123",
                            "created_at": "2026-02-02T10:00:00Z",
                            "updated_at": None,
                        }
                    ],
                }
            }
        }
    },
)
async def list_active_channels(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[ChannelRead]:
    await get_agent_or_404(agent_id, db, user)
    stmt = (
        select(Channel)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.is_deleted.is_(False),
            or_(
                Channel.type != "telegram",
                Channel.telegram_webhook_enabled.is_(True),
            ),
        )
        .order_by(Channel.created_at.desc())
    )
    result = await db.execute(stmt)
    channels = result.scalars().all()
    return [ChannelRead.model_validate(channel) for channel in channels]


@router.get(
    "/{agent_id}/channels/{channel_type}/auth/qr",
    response_model=ChannelAuthQrRead,
    summary="Получить QR для авторизации номера",
)
async def get_channel_auth_qr(
    agent_id: UUID,
    channel_type: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ChannelAuthQrRead:
    await get_agent_or_404(agent_id, db, user)
    resolved_type = _resolve_channel_type_from_path(channel_type.lower())
    if resolved_type not in WAPPI_PHONE_CHANNEL_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="QR авторизация доступна только для подключаемых номеров",
        )
    channel, _ = await _get_channel_for_agent_by_type_or_404(db, agent_id, resolved_type)
    try:
        qr_result = await request_channel_auth_qr(channel=channel)
    except ChannelProfileConfigError as exc:
        wappi_webhook_logger.warning(
            "channel_phone_qr_config_error",
            agent_id=str(agent_id),
            channel_type=resolved_type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Сервис авторизации канала сейчас недоступен",
        ) from exc
    except ChannelProfileUnsupportedTypeError as exc:
        wappi_webhook_logger.warning(
            "channel_phone_qr_unsupported_type",
            agent_id=str(agent_id),
            channel_type=resolved_type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Выбранный тип канала не поддерживается",
        ) from exc
    except ChannelProfileNotBoundError as exc:
        wappi_webhook_logger.warning(
            "channel_phone_qr_not_ready",
            agent_id=str(agent_id),
            channel_type=resolved_type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Канал еще не готов к авторизации",
        ) from exc
    except ChannelProfileExternalError as exc:
        wappi_webhook_logger.warning(
            "channel_phone_qr_external_error",
            agent_id=str(agent_id),
            channel_type=resolved_type,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось получить QR-код. Попробуйте позже",
        ) from exc

    return ChannelAuthQrRead(
        status=qr_result.status,
        qr_code=qr_result.qr_code,
        uuid=qr_result.uuid,
        time=qr_result.time,
        timestamp=qr_result.timestamp,
    )


@router.post(
    "/{agent_id}/channels",
    response_model=ChannelRead,
    status_code=status.HTTP_201_CREATED,
    summary="Подключить канал",
    response_description="Подключенный канал",
)
async def connect_channel(
    agent_id: UUID,
    payload: ChannelConnectionPayload,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ChannelRead:
    agent = await get_agent_or_404(agent_id, db, user)
    agent_id_str = str(agent_id)
    resolved_type = _resolve_channel_type(payload.type)
    stmt = (
        select(Channel.id)
        .join(AgentChannel, AgentChannel.channel_id == Channel.id)
        .where(
            AgentChannel.agent_id == agent_id,
            Channel.type == resolved_type,
            Channel.is_deleted.is_(False),
        )
        .limit(1)
    )
    existing = await db.execute(stmt)
    if existing.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel already connected",
        )
    channel = Channel(type=resolved_type)
    if resolved_type == "telegram":
        channel.telegram_bot_token = payload.telegram_bot_token
        channel.telegram_webhook_enabled = True
    db.add(channel)
    await db.flush()
    db.add(AgentChannel(agent_id=agent.id, channel_id=channel.id))
    if resolved_type == "telegram":
        _ensure_telegram_webhook(channel)
        webhook_url = _build_public_webhook_url(channel.telegram_webhook_endpoint or "")
        try:
            await set_telegram_webhook(
                bot_token=channel.telegram_bot_token or "",
                webhook_url=webhook_url,
                secret_token=channel.telegram_webhook_secret or "",
            )
        except TelegramWebhookError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Telegram setWebhook failed",
            ) from exc
        _log_telegram_webhook_connected(agent_id=agent.id, channel=channel, action="connect")
    elif resolved_type in WAPPI_PHONE_CHANNEL_TYPES:
        try:
            webhook_url = _build_public_webhook_url(_build_phone_channel_webhook_endpoint(channel.id))
            await bind_profile_to_channel(
                db=db,
                channel=channel,
                profile_name=_build_wappi_profile_name(agent.name, resolved_type, channel.id),
                webhook_url=webhook_url,
            )
        except HTTPException:
            await db.rollback()
            raise
        except ChannelProfileConfigError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_connect_config_error",
                agent_id=agent_id_str,
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Сервис подключения канала сейчас недоступен",
            ) from exc
        except ChannelProfileUnsupportedTypeError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_connect_unsupported_type",
                agent_id=agent_id_str,
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Выбранный тип канала не поддерживается",
            ) from exc
        except ChannelProfileExternalError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_connect_external_error",
                agent_id=agent_id_str,
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось подключить номер мессенджера. Попробуйте позже",
            ) from exc
    await db.commit()
    await db.refresh(channel)
    await write_audit(db, user, "agent.channel.connect", "agent", str(agent.id))
    return ChannelRead.model_validate(channel)


@router.put(
    "/{agent_id}/channels",
    response_model=ChannelRead,
    summary="Обновить канал",
    response_description="Обновленный канал",
)
async def update_channel(
    agent_id: UUID,
    payload: ChannelConnectionPayload,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> ChannelRead:
    await get_agent_or_404(agent_id, db, user)
    resolved_type = _resolve_channel_type(payload.type)
    channel, _link = await _get_channel_for_agent_by_type_or_404(db, agent_id, resolved_type)
    if resolved_type == "telegram":
        channel.telegram_bot_token = payload.telegram_bot_token
        channel.telegram_webhook_enabled = True
        _ensure_telegram_webhook(channel)
        webhook_url = _build_public_webhook_url(channel.telegram_webhook_endpoint or "")
        try:
            await set_telegram_webhook(
                bot_token=channel.telegram_bot_token or "",
                webhook_url=webhook_url,
                secret_token=channel.telegram_webhook_secret or "",
            )
        except TelegramWebhookError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Telegram setWebhook failed",
            ) from exc
        _log_telegram_webhook_connected(agent_id=agent_id, channel=channel, action="update")
    await db.commit()
    await db.refresh(channel)
    await write_audit(db, user, "agent.channel.update", "agent", str(agent_id))
    return ChannelRead.model_validate(channel)


def _resolve_channel_type_from_path(channel_type: str) -> str:
    """Path segment 'telegram' | 'telegram_phone' | 'whatsapp' | 'max' -> internal type."""
    if channel_type not in CHANNEL_TYPE_MAP.values():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported channel type; use 'telegram', 'telegram_phone', 'whatsapp' or 'max'",
        )
    return channel_type


@router.delete(
    "/{agent_id}/channels/{channel_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отключить канал по типу (из пути)",
    description="Удаляет привязку канала к агенту. Тип в пути: telegram, telegram_phone, whatsapp или max.",
)
async def disconnect_channel_by_type(
    agent_id: UUID,
    channel_type: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await get_agent_or_404(agent_id, db, user)
    resolved_type = _resolve_channel_type_from_path(channel_type.lower())
    channel, link = await _get_channel_for_agent_by_type_or_404(db, agent_id, resolved_type)
    if resolved_type in WAPPI_PHONE_CHANNEL_TYPES:
        try:
            await unbind_profile_from_channel(
                db=db,
                channel=channel,
                ignore_missing=True,
            )
        except ChannelProfileConfigError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_disconnect_config_error",
                agent_id=str(agent_id),
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Сервис подключения канала сейчас недоступен",
            ) from exc
        except ChannelProfileUnsupportedTypeError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_disconnect_unsupported_type",
                agent_id=str(agent_id),
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Выбранный тип канала не поддерживается",
            ) from exc
        except ChannelProfileExternalError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_disconnect_external_error",
                agent_id=str(agent_id),
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось отключить номер мессенджера. Попробуйте позже",
            ) from exc
    await db.delete(link)
    await db.flush()
    stmt = select(AgentChannel.id).where(AgentChannel.channel_id == channel.id)
    remaining = await db.execute(stmt)
    if remaining.scalar_one_or_none() is None:
        channel.is_deleted = True
        channel.deleted_at = datetime.utcnow()
    await db.commit()
    await write_audit(db, user, "agent.channel.disconnect", "agent", str(agent_id))
    return None


@router.delete(
    "/{agent_id}/channels",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отключить канал (тип в теле)",
    description="Удаляет привязку канала. Тип в теле: type = Telegram_Bot | Telegram_Phone | Whatsapp_Phone | Max_Phone.",
)
async def disconnect_channel(
    agent_id: UUID,
    payload: ChannelDisconnectPayload,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await get_agent_or_404(agent_id, db, user)
    resolved_type = _resolve_channel_type(payload.type)
    channel, link = await _get_channel_for_agent_by_type_or_404(db, agent_id, resolved_type)
    if resolved_type in WAPPI_PHONE_CHANNEL_TYPES:
        try:
            await unbind_profile_from_channel(
                db=db,
                channel=channel,
                ignore_missing=True,
            )
        except ChannelProfileConfigError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_disconnect_config_error",
                agent_id=str(agent_id),
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Сервис подключения канала сейчас недоступен",
            ) from exc
        except ChannelProfileUnsupportedTypeError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_disconnect_unsupported_type",
                agent_id=str(agent_id),
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Выбранный тип канала не поддерживается",
            ) from exc
        except ChannelProfileExternalError as exc:
            await db.rollback()
            wappi_webhook_logger.warning(
                "channel_phone_disconnect_external_error",
                agent_id=str(agent_id),
                channel_type=resolved_type,
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Не удалось отключить номер мессенджера. Попробуйте позже",
            ) from exc
    await db.delete(link)
    await db.flush()
    stmt = select(AgentChannel.id).where(AgentChannel.channel_id == channel.id)
    remaining = await db.execute(stmt)
    if remaining.scalar_one_or_none() is None:
        channel.is_deleted = True
        channel.deleted_at = datetime.utcnow()
    await db.commit()
    await write_audit(db, user, "agent.channel.disconnect", "agent", str(agent_id))
    return None
