from __future__ import annotations

import json
import structlog
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_404, require_scope
from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.models.run import Run
from app.db.models.session_message import SessionMessage
from app.db.session import async_session_factory, get_db
from app.schemas.auth import AuthContext
from app.schemas.run import RunCreate, RunRead
from app.services.logfire_cost_reconcile import schedule_logfire_cost_reconcile
from app.services.run_service import (
    execute_agent_run,
    load_agent_and_tools,
    get_session_history,
)
from app.services.runtime import logger as runtime_logger
from app.services.tool_executor import ToolExecutionError

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("", response_model=RunRead, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_settings().rate_limit_runs)
async def create_run(
    payload: RunCreate,
    request: Request,  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("runs:write")),
) -> RunRead:
    agent, tools, bindings = await load_agent_and_tools(db, payload.agent_id, user.tenant_id)

    session_id = payload.session_id or str(uuid4())
    message_history = await get_session_history(db, session_id, user.tenant_id, agent.id, limit=agent.max_history_messages)

    trace_id = str(uuid4())
    run = Run(
        tenant_id=user.tenant_id,
        agent_id=agent.id,
        session_id=session_id,
        status="running",
        input_message=payload.input_message,
        trace_id=trace_id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    execution_result = None
    try:
        execution_result = await execute_agent_run(
            db,
            agent=agent,
            tools=tools,
            bindings=bindings,
            run=run,
            input_message=payload.input_message,
            trace_id=trace_id,
            user=user,
            session_id=session_id,
            message_history=message_history,
        )
    except ToolExecutionError as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
    except Exception as exc:  # noqa: BLE001
        logger.exception("run_failed", trace_id=trace_id, error=str(exc))
        run.status = "failed"
        run.error_message = f"Runtime error: {str(exc)}"
        run.logfire_reconcile_status = "skipped"
        run.logfire_reconcile_error = "run_failed"
    finally:
        run.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(run)

    if run.status == "succeeded":
        schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)

    response = RunRead.model_validate(run)
    if execution_result and execution_result.orchestration_meta:
        response.orchestration_meta = execution_result.orchestration_meta
    return response


@router.post("/stream")
@limiter.limit(get_settings().rate_limit_runs)
async def stream_run(
    payload: RunCreate,
    request: Request,  # noqa: ARG001
    user: AuthContext = Depends(require_scope("runs:write")),
) -> EventSourceResponse:
    settings = get_settings()
    trace_id = str(uuid4())
    session_id = payload.session_id or str(uuid4())

    async def event_generator():
        async with async_session_factory() as session:
            agent, tools, bindings = await load_agent_and_tools(session, payload.agent_id, user.tenant_id)
            message_history = await get_session_history(session, session_id, user.tenant_id, agent.id, limit=agent.max_history_messages)

            run = Run(
                tenant_id=user.tenant_id,
                agent_id=agent.id,
                session_id=session_id,
                status="running",
                input_message=payload.input_message,
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
                agent, tools, bindings = await load_agent_and_tools(session, payload.agent_id, user.tenant_id)
                result = await execute_agent_run(
                    session,
                    agent=agent,
                    tools=tools,
                    bindings=bindings,
                    run=run,
                    input_message=payload.input_message,
                    trace_id=trace_id,
                    user=user,
                    session_id=session_id,
                    message_history=message_history,
                )
                await session.merge(run)
                await session.commit()
                schedule_logfire_cost_reconcile(run_id=run.id, trace_id=trace_id)
                yield {"event": "result", "data": json.dumps({"output": result.output})}
            except ToolExecutionError as exc:
                run.status = "failed"
                run.error_message = str(exc)
                run.logfire_reconcile_status = "skipped"
                run.logfire_reconcile_error = "run_failed"
                await session.merge(run)
                await session.commit()
                yield {"event": "error", "data": json.dumps({"error": str(exc)})}
            except Exception as exc:  # noqa: BLE001
                runtime_logger.exception("stream_run_failed", trace_id=trace_id, error=str(exc))
                run.status = "failed"
                run.error_message = f"Runtime error: {str(exc)}"
                run.logfire_reconcile_status = "skipped"
                run.logfire_reconcile_error = "run_failed"
                await session.merge(run)
                await session.commit()
                yield {"event": "error", "data": json.dumps({"error": f"Runtime error: {str(exc)}"})}

    return EventSourceResponse(event_generator(), ping=settings.sse_keepalive_seconds)


@router.get("/{run_id}", response_model=RunRead)
async def get_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("runs:read")),
) -> RunRead:
    run = await get_or_404(db, Run, id=run_id, tenant_id=user.tenant_id, label="Run")
    return RunRead.model_validate(run)


@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("dialogs:delete")),
) -> None:
    await db.execute(
        delete(SessionMessage).where(
            SessionMessage.session_id == session_id,
            SessionMessage.tenant_id == user.tenant_id,
        )
    )
    stmt = delete(Run).where(
        Run.session_id == session_id,
        Run.tenant_id == user.tenant_id,
    )
    await db.execute(stmt)
    await db.commit()
