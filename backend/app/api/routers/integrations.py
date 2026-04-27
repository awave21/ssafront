"""Integration API router for public endpoints."""

from __future__ import annotations

import json
import structlog
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps_integration import IntegrationContext, get_integration_context
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.session import async_session_factory, get_db
from app.schemas.integration import ChatHistoryResponse, ChatMessage, ChatRequest, ChatResponse
from app.services.logfire_cost_reconcile import schedule_logfire_cost_reconcile
from app.services.run_service import (
    execute_agent_run,
    load_agent_and_tools,
    get_session_history,
)
from app.services.runtime import logger as runtime_logger
from app.services.tool_executor import ToolExecutionError
from app.utils.message_mapping import extract_text_contents, infer_role

router = APIRouter()
logger = structlog.get_logger(__name__)


def _integration_chat_role_display(raw_role: str) -> str:
    """Роль для публичного API: agent → assistant (привычнее клиентам)."""
    if raw_role == "agent":
        return "assistant"
    return raw_role


def _integration_chat_plain_text(msg_data: dict) -> str:
    chunks = extract_text_contents(msg_data)
    return "\n".join(chunks).strip()


def _tool_names_from_run(run: Run) -> list[str]:
    names: list[str] = []
    for item in run.tools_called or []:
        if isinstance(item, dict):
            n = item.get("name")
            if isinstance(n, str) and n.strip():
                names.append(n.strip())
    return names


async def _run_chat(
    message: str,
    session_id: str | None,
    ctx: IntegrationContext,
    db: AsyncSession,
) -> ChatResponse:
    """Shared logic for all chat entry points."""
    agent, tools, bindings = await load_agent_and_tools(db, ctx.agent_id, ctx.tenant_id)

    effective_session_id = session_id or f"integration:{ctx.api_key_id}:{uuid4()}"

    message_history = await get_session_history(
        db, effective_session_id, ctx.tenant_id, ctx.agent_id, limit=agent.max_history_messages
    )

    logger.info(
        "integration_chat_debug",
        effective_session_id=effective_session_id,
        agent_id=str(ctx.agent_id),
        tenant_id=str(ctx.tenant_id),
        history_is_none=message_history is None,
        history_length=len(message_history) if message_history else 0,
        history_types=[type(m).__name__ for m in (message_history or [])[:5]],
        history_preview=[
            str(getattr(m, "parts", ["no parts"]))[:120]
            for m in (message_history or [])[:4]
        ],
        max_history_messages=agent.max_history_messages,
    )

    trace_id = str(uuid4())
    run = Run(
        tenant_id=ctx.tenant_id,
        agent_id=ctx.agent_id,
        session_id=effective_session_id,
        status="running",
        input_message=message,
        trace_id=trace_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.schemas.auth import AuthContext
    auth_ctx = AuthContext(
        user_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        role="integration",
        scopes=ctx.scopes,
    )

    try:
        await execute_agent_run(
            db,
            agent=agent,
            tools=tools,
            bindings=bindings,
            run=run,
            input_message=message,
            trace_id=trace_id,
            user=auth_ctx,
            session_id=effective_session_id,
            message_history=message_history,
        )
    except ToolExecutionError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
    except Exception as exc:  # noqa: BLE001
        logger.exception("integration_run_failed", trace_id=trace_id, error=str(exc))
        run.status = "failed"
        run.error_message = f"Runtime error: {str(exc)}"
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
    finally:
        run.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run)

    if run.status == "succeeded":
        schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)

    return ChatResponse(
        response=run.output_message or "",
        session_id=effective_session_id,
        run_id=run.id,
        tool_names=_tool_names_from_run(run),
    )


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(get_settings().rate_limit_integrations)
async def chat(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message to the agent.

    Accepts parameters from query string, JSON body, or both (query takes priority).

    1) Query params only:
       POST /integrations/chat?api_key=sk-...&message=Hello&session_id=optional

    2) JSON body + header:
       POST /integrations/chat
       Header: x-api-key: sk-...
       Body: {"message": "...", "session_id": "..."}

    3) Mix: api_key in query, message in body, etc.
    """
    query = request.query_params
    q_message = query.get("message")
    q_session_id = query.get("session_id")
    q_api_key = query.get("api_key")

    body: dict = {}
    if not q_message or not q_api_key:
        try:
            body = await request.json()
        except Exception:
            pass

    raw_message = q_message or body.get("message")
    raw_session_id = q_session_id or body.get("session_id")
    raw_api_key = q_api_key or request.headers.get("x-api-key") or body.get("api_key")

    effective_message = str(raw_message) if raw_message is not None else None
    effective_session_id = str(raw_session_id) if raw_session_id is not None else None
    effective_api_key = str(raw_api_key) if raw_api_key is not None else None

    if not effective_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "missing_message", "message": "Parameter 'message' is required (query, body, or header)"},
        )

    if not effective_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "missing_key", "message": "API key required: query 'api_key', header 'x-api-key', or body 'api_key'"},
        )

    ctx = await get_integration_context(x_api_key=effective_api_key, db=db)
    return await _run_chat(effective_message, effective_session_id, ctx, db)


@router.post("/chat/stream")
async def stream_chat(
    payload: ChatRequest,
    ctx: IntegrationContext = Depends(get_integration_context),
) -> EventSourceResponse:
    """Stream chat response via SSE."""
    trace_id = str(uuid4())
    session_id = payload.session_id or f"integration:{ctx.api_key_id}:{uuid4()}"

    from app.schemas.auth import AuthContext
    auth_ctx = AuthContext(
        user_id=ctx.user_id,
        tenant_id=ctx.tenant_id,
        role="integration",
        scopes=ctx.scopes,
    )

    async def event_generator():
        async with async_session_factory() as session:
            agent, tools, bindings = await load_agent_and_tools(
                session, ctx.agent_id, ctx.tenant_id
            )
            message_history = await get_session_history(
                session, session_id, ctx.tenant_id, ctx.agent_id, limit=agent.max_history_messages
            )

            run = Run(
                tenant_id=ctx.tenant_id,
                agent_id=ctx.agent_id,
                session_id=session_id,
                status="running",
                input_message=payload.message,
                trace_id=trace_id,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

        yield {
            "event": "start",
            "data": json.dumps({"run_id": str(run.id), "trace_id": trace_id}),
        }

        async with async_session_factory() as session:
            try:
                agent, tools, bindings = await load_agent_and_tools(
                    session, ctx.agent_id, ctx.tenant_id
                )
                result = await execute_agent_run(
                    session,
                    agent=agent,
                    tools=tools,
                    bindings=bindings,
                    run=run,
                    input_message=payload.message,
                    trace_id=trace_id,
                    user=auth_ctx,
                    session_id=session_id,
                    message_history=message_history,
                )
                await session.merge(run)
                await session.commit()
                schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)
                yield {
                    "event": "result",
                    "data": json.dumps(
                        {
                            "output": result.output,
                            "tool_names": _tool_names_from_run(run),
                        }
                    ),
                }
            except ToolExecutionError as exc:
                run.status = "failed"
                run.error_message = str(exc)
                run.logfire_reconcile_status = "skipped"
                yield {"event": "error", "data": json.dumps({"error": str(exc)})}
            except Exception as exc:  # noqa: BLE001
                logger.exception("integration_stream_failed", trace_id=trace_id)
                run.status = "failed"
                run.error_message = f"Runtime error: {str(exc)}"
                yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(event_generator())


@router.get("/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    ctx: IntegrationContext = Depends(get_integration_context),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """История сессии: сообщения в формате pydantic-ai (parts) разворачиваются в текст."""
    stmt = (
        select(SessionMessage)
        .join(Run, SessionMessage.run_id == Run.id)
        .where(
            SessionMessage.tenant_id == ctx.tenant_id,
            SessionMessage.session_id == session_id,
            Run.agent_id == ctx.agent_id,
        )
        .order_by(SessionMessage.message_index.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    chat_messages = []
    for msg in messages:
        msg_data = msg.message if isinstance(msg.message, dict) else {}
        role_raw = infer_role(msg_data)
        content = _integration_chat_plain_text(msg_data)
        chat_messages.append(
            ChatMessage(
                role=_integration_chat_role_display(role_raw),
                content=content,
                created_at=msg.created_at,
            )
        )

    return ChatHistoryResponse(messages=chat_messages)
