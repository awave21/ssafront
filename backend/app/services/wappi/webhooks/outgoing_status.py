from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routers.webhooks_inbound_agent import append_wappi_linked_account_message
from app.db.models.agent import Agent
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.services.wappi.webhooks.message_normalizer import (
    delivery_status_rank,
    extract_manager_text,
    message_has_failed_status,
    message_is_manager,
    normalize_delivery_status,
    outbound_channel_type_from_payload,
)
from app.utils.broadcast import broadcaster


async def find_outgoing_message_candidate(
    db: AsyncSession,
    *,
    agent_id: UUID,
    agent: Agent,
    session_id: str,
    channel_type: str,
    provider_message_id: str | None = None,
    provider_task_id: str | None = None,
    provider_uuid: str | None = None,
    text_hint: str | None = None,
) -> SessionMessage | None:
    exact_lookups: list[tuple[str, str]] = []
    if provider_message_id:
        exact_lookups.append(("provider_message_id", provider_message_id))
    if provider_task_id:
        exact_lookups.append(("provider_task_id", provider_task_id))
    if provider_uuid:
        exact_lookups.append(("provider_uuid", provider_uuid))

    for metadata_key, metadata_value in exact_lookups:
        stmt = (
            select(SessionMessage)
            .join(Run, Run.id == SessionMessage.run_id)
            .where(
                SessionMessage.tenant_id == agent.tenant_id,
                SessionMessage.session_id == session_id,
                Run.agent_id == agent_id,
                SessionMessage.message[metadata_key].astext == metadata_value,
            )
            .order_by(SessionMessage.message_index.desc())
            .limit(1)
        )
        message = (await db.execute(stmt)).scalar_one_or_none()
        if message is not None:
            return message

    if not text_hint:
        return None

    stmt = (
        select(SessionMessage)
        .join(Run, Run.id == SessionMessage.run_id)
        .where(
            SessionMessage.tenant_id == agent.tenant_id,
            SessionMessage.session_id == session_id,
            Run.agent_id == agent_id,
        )
        .order_by(SessionMessage.message_index.desc())
        .limit(30)
    )
    candidates = (await db.execute(stmt)).scalars().all()
    normalized_hint = text_hint.strip()
    if not normalized_hint:
        return None

    for candidate in candidates:
        payload = candidate.message if isinstance(candidate.message, dict) else {}
        if not payload or not message_is_manager(payload):
            continue
        if message_has_failed_status(payload):
            continue
        payload_channel_type = outbound_channel_type_from_payload(payload)
        if payload_channel_type and payload_channel_type != channel_type:
            continue
        if extract_manager_text(payload) != normalized_hint:
            continue
        created_at = candidate.created_at
        created_at_naive = created_at.replace(tzinfo=None) if created_at and created_at.tzinfo else created_at
        if created_at_naive and (datetime.utcnow() - created_at_naive).total_seconds() > 3600:
            continue
        return candidate
    return None


async def update_outgoing_message(
    db: AsyncSession,
    *,
    agent_id: UUID,
    session_id: str,
    session_message: SessionMessage,
    status_value: str,
    provider_message_id: str | None = None,
    provider_task_id: str | None = None,
    provider_uuid: str | None = None,
    wh_type: str | None = None,
) -> bool:
    message_payload = session_message.message if isinstance(session_message.message, dict) else {}
    message_payload = {**message_payload}
    current_status = normalize_delivery_status(message_payload.get("status")) or "sent"
    if delivery_status_rank(status_value) < delivery_status_rank(current_status):
        return False

    message_payload["status"] = status_value
    if wh_type:
        message_payload["wappi_wh_type"] = wh_type
    if provider_message_id:
        message_payload["provider_message_id"] = provider_message_id
    if provider_task_id:
        message_payload["provider_task_id"] = provider_task_id
    if provider_uuid:
        message_payload["provider_uuid"] = provider_uuid
    message_payload["delivery_status_updated_at"] = datetime.utcnow().isoformat()
    session_message.message = message_payload
    await db.commit()

    await broadcaster.publish(
        agent_id,
        {
            "type": "message_updated",
            "data": {
                "id": str(session_message.id),
                "session_id": session_id,
                "agent_id": str(agent_id),
                "status": status_value,
                "provider_message_id": provider_message_id,
            },
        },
    )
    return True


async def update_wappi_phone_outgoing_status(
    db: AsyncSession,
    *,
    agent_id: UUID,
    agent: Agent,
    session_id: str,
    channel_type: str,
    provider_message_id: str | None,
    provider_task_id: str | None,
    provider_uuid: str | None,
    new_status: str,
) -> bool:
    session_message = await find_outgoing_message_candidate(
        db,
        agent_id=agent_id,
        agent=agent,
        session_id=session_id,
        channel_type=channel_type,
        provider_message_id=provider_message_id,
        provider_task_id=provider_task_id,
        provider_uuid=provider_uuid,
    )
    if session_message is None:
        return False
    return await update_outgoing_message(
        db,
        agent_id=agent_id,
        session_id=session_id,
        session_message=session_message,
        status_value=new_status,
        provider_message_id=provider_message_id,
        provider_task_id=provider_task_id,
        provider_uuid=provider_uuid,
    )


async def link_or_append_wappi_operator_message(
    db: AsyncSession,
    *,
    agent_id: UUID,
    agent: Agent,
    session_id: str,
    input_text: str,
    base_user_info: dict[str, Any],
    log_source: str,
    wh_type: str,
    channel_type: str,
    initial_status: str,
    provider_message_id: str | None,
    provider_task_id: str | None,
    provider_uuid: str | None,
) -> None:
    candidate = await find_outgoing_message_candidate(
        db,
        agent_id=agent_id,
        agent=agent,
        session_id=session_id,
        channel_type=channel_type,
        provider_message_id=provider_message_id,
        provider_task_id=provider_task_id,
        provider_uuid=provider_uuid,
        text_hint=input_text,
    )
    if candidate is not None:
        await update_outgoing_message(
            db,
            agent_id=agent_id,
            session_id=session_id,
            session_message=candidate,
            status_value=initial_status,
            provider_message_id=provider_message_id,
            provider_task_id=provider_task_id,
            provider_uuid=provider_uuid,
            wh_type=wh_type,
        )
        return

    message_metadata: dict[str, Any] = {
        "status": initial_status,
        "wappi_wh_type": wh_type,
        "outbound_channel_type": channel_type,
    }
    if provider_message_id:
        message_metadata["provider_message_id"] = provider_message_id
    if provider_task_id:
        message_metadata["provider_task_id"] = provider_task_id
    if provider_uuid:
        message_metadata["provider_uuid"] = provider_uuid
    await append_wappi_linked_account_message(
        db,
        agent,
        session_id=session_id,
        text=input_text,
        base_user_info=base_user_info,
        log_source=log_source,
        message_metadata=message_metadata,
    )
