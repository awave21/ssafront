from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.webhooks_inbound_agent import process_webhook_inbound_agent_message
from app.api.routers.webhooks_utils import sanitize_agent_reply_text
from app.db.models.agent import Agent
from app.db.models.channel import Channel
from app.db.models.tenant import Tenant
from app.schemas.auth import AuthContext
from app.services.function_rules_runtime import run_rules_for_phase
from app.services.agent_user_state import is_agent_user_disabled
from app.services.dialog_state import is_dialog_active, is_manager_paused
from app.services.wappi import WappiClientError
from app.services.wappi.binding import ChannelProfileConfigError
from app.services.wappi.webhooks.message_normalizer import (
    WAPPI_DELIVERY_EVENT_TYPES,
    coerce_message_dicts,
    coerce_bool,
    extract_provider_message_id,
    extract_provider_task_id,
    extract_provider_uuid,
    is_private_chat,
    is_text_message,
    likely_api_automated_send,
    normalize_delivery_status,
    phone_operator_user_info,
)
from app.services.wappi.webhooks.outgoing_status import (
    link_or_append_wappi_operator_message,
    update_wappi_phone_outgoing_status,
)

logger = structlog.get_logger()


async def _run_send_error_scenario_rules(
    db: AsyncSession,
    *,
    agent: Agent,
    session_id: str,
    input_text: str,
    user_info: dict[str, Any],
    error_message: str,
) -> None:
    tenant = await db.get(Tenant, agent.tenant_id)
    rules_enabled = bool(getattr(agent, "function_rules_enabled", True)) and bool(
        getattr(tenant, "function_rules_enabled", True) if tenant else True
    )
    semantic_allowed = bool(getattr(agent, "function_rules_allow_semantic", True)) and bool(
        getattr(tenant, "function_rules_allow_semantic", True) if tenant else True
    )
    if not rules_enabled:
        return
    webhook_user = AuthContext(
        user_id=agent.owner_user_id,
        tenant_id=agent.tenant_id,
        scopes=["tools:write"],
    )
    trace_id = str(uuid4())
    try:
        await run_rules_for_phase(
            db,
            tenant_id=agent.tenant_id,
            agent_id=agent.id,
            session_id=session_id,
            trace_id=trace_id,
            phase="send_error",
            message=input_text or "",
            user=webhook_user,
            run_id=None,
            context={
                "user_info": user_info,
                "send_error": error_message,
                "agent_timezone": getattr(agent, "timezone", None) or "UTC",
                "input_message": input_text,
                "message": input_text,
            },
            rules_enabled=True,
            semantic_allowed=semantic_allowed,
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "send_error_scenario_rules_failed",
            agent_id=str(agent.id),
            session_id=session_id,
            error=str(exc),
        )


@dataclass(frozen=True)
class WappiProviderRefs:
    provider_message_id: str | None
    provider_task_id: str | None
    provider_uuid: str | None


@dataclass(frozen=True)
class InboundMessageContext:
    session_id: str
    input_text: str
    user_info: dict[str, Any]
    platform_user_id: str
    linked_account_message: bool
    raw_msg: dict[str, Any]
    send_payload: dict[str, Any]


@dataclass(frozen=True)
class WappiChannelStrategy:
    channel_type: str
    user_disabled_platform: str
    run_log_source: str
    operator_log_source: str
    delivery_not_found_event: str
    delivery_update_failed_event: str
    operator_message_failed_event: str
    message_skipped_event: str
    save_without_agent_failed_event: str
    send_reply_failed_event: str
    is_text_event: Callable[[str], bool]
    is_platform_supported: Callable[[dict[str, Any]], bool]
    resolve_delivery_session_id: Callable[[dict[str, Any]], str | None]
    build_inbound_context: Callable[[dict[str, Any], Channel, UUID], InboundMessageContext | None]
    send_reply: Callable[[Channel, UUID, str, InboundMessageContext], Awaitable[None]]


async def _handle_delivery_event(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    raw_msg: dict[str, Any],
    provider_refs: WappiProviderRefs,
    strategy: WappiChannelStrategy,
) -> None:
    delivery_status = normalize_delivery_status(raw_msg.get("status"))
    session_id = strategy.resolve_delivery_session_id(raw_msg)
    if not delivery_status or not session_id:
        return
    try:
        updated = await update_wappi_phone_outgoing_status(
            db,
            agent_id=agent_id,
            agent=agent,
            session_id=session_id,
            channel_type=strategy.channel_type,
            provider_message_id=provider_refs.provider_message_id,
            provider_task_id=provider_refs.provider_task_id,
            provider_uuid=provider_refs.provider_uuid,
            new_status=delivery_status,
        )
        if not updated:
            logger.info(
                strategy.delivery_not_found_event,
                channel_id=str(channel.id),
                agent_id=str(agent_id),
                session_id=session_id,
                provider_message_id=provider_refs.provider_message_id,
                status=delivery_status,
            )
    except Exception as exc:
        logger.exception(
            strategy.delivery_update_failed_event,
            channel_id=str(channel.id),
            agent_id=str(agent_id),
            provider_message_id=provider_refs.provider_message_id,
            status=delivery_status,
            error=str(exc),
        )


async def _handle_linked_account_message(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    context: InboundMessageContext,
    wh_type: str,
    provider_refs: WappiProviderRefs,
    strategy: WappiChannelStrategy,
) -> None:
    if likely_api_automated_send(context.raw_msg):
        return
    try:
        operator_user_info = phone_operator_user_info(context.user_info, channel_type=channel.type)
        initial_status = normalize_delivery_status(context.raw_msg.get("status")) or "sent"
        await link_or_append_wappi_operator_message(
            db,
            agent_id=agent_id,
            agent=agent,
            session_id=context.session_id,
            input_text=context.input_text,
            base_user_info=operator_user_info,
            log_source=strategy.operator_log_source,
            wh_type=wh_type,
            channel_type=strategy.channel_type,
            initial_status=initial_status,
            provider_message_id=provider_refs.provider_message_id,
            provider_task_id=provider_refs.provider_task_id,
            provider_uuid=provider_refs.provider_uuid,
        )
    except Exception as exc:
        logger.exception(
            strategy.operator_message_failed_event,
            channel_id=str(channel.id),
            agent_id=str(agent_id),
            session_id=context.session_id,
            error=str(exc),
        )


async def _handle_inbound_message(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    context: InboundMessageContext,
    strategy: WappiChannelStrategy,
) -> None:
    dialog_active = await is_dialog_active(db, agent_id, context.session_id)
    manager_paused = False
    if dialog_active:
        manager_paused = await is_manager_paused(db, agent_id, context.session_id)

    user_disabled = await is_agent_user_disabled(
        db,
        tenant_id=agent.tenant_id,
        agent_id=agent_id,
        platform=strategy.user_disabled_platform,
        platform_user_id=context.platform_user_id,
    )

    should_run_agent = (
        dialog_active
        and not manager_paused
        and not agent.is_disabled
        and not user_disabled
    )

    if should_run_agent:
        reply = await process_webhook_inbound_agent_message(
            db,
            agent,
            session_id=context.session_id,
            input_text=context.input_text,
            user_info=context.user_info,
            run_agent=True,
            log_source=strategy.run_log_source,
        )
        if reply:
            reply_text = sanitize_agent_reply_text(reply)
            if reply_text:
                try:
                    await strategy.send_reply(channel, agent_id, reply_text, context)
                except (WappiClientError, ChannelProfileConfigError) as exc:
                    logger.warning(
                        strategy.send_reply_failed_event,
                        channel_id=str(channel.id),
                        agent_id=str(agent_id),
                        error=str(exc),
                    )
                    await _run_send_error_scenario_rules(
                        db,
                        agent=agent,
                        session_id=context.session_id,
                        input_text=context.input_text,
                        user_info=context.user_info,
                        error_message=str(exc),
                    )
        return

    if agent.is_disabled:
        skip_reason = "agent_disabled"
    elif user_disabled:
        skip_reason = "agent_user_disabled"
    elif manager_paused:
        skip_reason = "manager_paused"
    else:
        skip_reason = "dialog_inactive"
    logger.info(
        strategy.message_skipped_event,
        reason=skip_reason,
        channel_id=str(channel.id),
        agent_id=str(agent_id),
        session_id=context.session_id,
    )
    try:
        await process_webhook_inbound_agent_message(
            db,
            agent,
            session_id=context.session_id,
            input_text=context.input_text,
            user_info=context.user_info,
            run_agent=False,
            log_source=strategy.run_log_source,
        )
    except Exception as exc:
        logger.exception(
            strategy.save_without_agent_failed_event,
            reason=skip_reason,
            channel_id=str(channel.id),
            agent_id=str(agent_id),
            error=str(exc),
        )


async def process_wappi_channel_messages(
    db: AsyncSession,
    *,
    channel: Channel,
    agent_id: UUID,
    agent: Agent,
    parsed_json: dict[str, Any],
    strategy: WappiChannelStrategy,
) -> None:
    for raw_msg in coerce_message_dicts(parsed_json):
        wh_type = str(raw_msg.get("wh_type") or "").strip().lower()
        provider_refs = WappiProviderRefs(
            provider_message_id=extract_provider_message_id(raw_msg),
            provider_task_id=extract_provider_task_id(raw_msg),
            provider_uuid=extract_provider_uuid(raw_msg),
        )

        if wh_type in WAPPI_DELIVERY_EVENT_TYPES:
            await _handle_delivery_event(
                db,
                channel=channel,
                agent_id=agent_id,
                agent=agent,
                raw_msg=raw_msg,
                provider_refs=provider_refs,
                strategy=strategy,
            )
            continue

        if not strategy.is_text_event(wh_type):
            continue
        if not strategy.is_platform_supported(raw_msg):
            continue
        if coerce_bool(raw_msg.get("is_bot")) is True:
            continue
        if not is_private_chat(raw_msg, channel_type=strategy.channel_type):
            continue
        if not is_text_message(raw_msg):
            continue

        context = strategy.build_inbound_context(raw_msg, channel, agent_id)
        if context is None:
            continue

        if context.linked_account_message:
            await _handle_linked_account_message(
                db,
                channel=channel,
                agent_id=agent_id,
                agent=agent,
                context=context,
                wh_type=wh_type,
                provider_refs=provider_refs,
                strategy=strategy,
            )
            continue

        await _handle_inbound_message(
            db,
            channel=channel,
            agent_id=agent_id,
            agent=agent,
            context=context,
            strategy=strategy,
        )
