from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from fastapi.exceptions import RequestValidationError
from starlette.requests import Request

from app.api.routers.agents import analysis as analysis_router
from app.main import _unhandled_exception_handler, _validation_error_handler
from app.schemas.agent_analysis import AnalysisJobCreateRequest
from app.schemas.auth import AuthContext
from app.services.agent_analysis.orchestrator import TerminalAnalysisJobError


class _DbStub:
    async def commit(self) -> None:
        return None

    async def refresh(self, _: object) -> None:
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job(*, status: str = "queued", stage: str = "queued", owner_id=None):
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=uuid4(),
        agent_id=uuid4(),
        status=status,
        stage=stage,
        progress_pct=0 if status == "queued" else 50,
        period_start=_now(),
        period_end=_now(),
        window_hours=24,
        only_with_manager=True,
        max_dialogs=100,
        history_limit=20,
        max_tokens_per_job=10000,
        max_llm_requests_per_job=30,
        idempotency_key=None,
        analysis_as_of=None,
        error_message=None,
        report_id=None,
        created_at=_now(),
        updated_at=_now(),
        started_at=None,
        finished_at=None,
        created_by_user_id=owner_id,
        cancelled_by_user_id=None,
        meta_model=None,
        tokens_used=0,
        llm_requests_used=0,
    )


def _user(*, role: str = "owner") -> AuthContext:
    return AuthContext(user_id=uuid4(), tenant_id=uuid4(), role=role, scopes=["agents:read", "agents:write"])


@pytest.mark.asyncio
async def test_start_analysis_job_returns_data_envelope_and_200_when_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    job = _job(owner_id=user.user_id)

    async def _noop_agent(*args, **kwargs):
        return None

    async def _create(*args, **kwargs):
        return job, False

    monkeypatch.setattr(analysis_router, "get_agent_or_404", _noop_agent)
    monkeypatch.setattr(analysis_router, "create_analysis_job", _create)
    response = Response()

    result = await analysis_router.start_analysis_job(
        agent_id=job.agent_id,
        payload=AnalysisJobCreateRequest(),
        response=response,
        db=_DbStub(),
        user=user,
    )

    assert response.status_code == 200
    assert result.data.id == job.id


@pytest.mark.asyncio
async def test_get_analysis_report_returns_409_when_job_not_succeeded(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    job = _job(status="running", stage="analyzing", owner_id=user.user_id)

    async def _noop_agent(*args, **kwargs):
        return None

    async def _get_job(*args, **kwargs):
        return job

    monkeypatch.setattr(analysis_router, "get_agent_or_404", _noop_agent)
    monkeypatch.setattr(analysis_router, "get_analysis_job", _get_job)

    with pytest.raises(HTTPException) as exc_info:
        await analysis_router.get_analysis_report(
            agent_id=job.agent_id,
            job_id=job.id,
            db=_DbStub(),
            user=user,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "report_not_ready"


@pytest.mark.asyncio
async def test_cancel_job_returns_409_for_terminal_status(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    job = _job(status="succeeded", stage="done", owner_id=user.user_id)

    async def _noop_agent(*args, **kwargs):
        return None

    async def _get_job(*args, **kwargs):
        return job

    async def _cancel(*args, **kwargs):
        raise TerminalAnalysisJobError(job)

    monkeypatch.setattr(analysis_router, "get_agent_or_404", _noop_agent)
    monkeypatch.setattr(analysis_router, "get_analysis_job", _get_job)
    monkeypatch.setattr(analysis_router, "cancel_analysis_job", _cancel)

    with pytest.raises(HTTPException) as exc_info:
        await analysis_router.cancel_job(
            agent_id=job.agent_id,
            job_id=job.id,
            db=_DbStub(),
            user=user,
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "analysis_job_terminal"


@pytest.mark.asyncio
async def test_get_recommendations_returns_items_total_limit_offset(monkeypatch: pytest.MonkeyPatch) -> None:
    user = _user()
    agent_id = uuid4()
    recommendation = SimpleNamespace(
        id=uuid4(),
        category="tool_needed",
        priority="high",
        confidence=0.9,
        title="Add validation tool",
        reasoning="Tool argument errors are frequent",
        suggestion="Create stricter tool schema",
        impact="Higher tool success",
        evidence_dialog_ids=["dlg-1"],
        evidence=[{"dialog_id": "dlg-1", "run_id": None, "message_id": None, "excerpt": "bad args"}],
        status="open",
        reviewer_comment=None,
        reviewed_at=None,
        reviewed_by_user_id=None,
        created_at=_now(),
        updated_at=_now(),
    )

    async def _noop_agent(*args, **kwargs):
        return None

    async def _list(*args, **kwargs):
        return [recommendation], 7

    monkeypatch.setattr(analysis_router, "get_agent_or_404", _noop_agent)
    monkeypatch.setattr(analysis_router, "list_recommendations", _list)

    result = await analysis_router.get_recommendations(
        agent_id=agent_id,
        category="tool_needed",
        status_filter="open",
        limit=25,
        offset=50,
        db=_DbStub(),
        user=user,
    )

    assert result.data.total == 7
    assert result.data.limit == 25
    assert result.data.offset == 50
    assert len(result.data.items) == 1


@pytest.mark.asyncio
async def test_validation_error_handler_returns_standard_payload() -> None:
    request = Request({"type": "http", "method": "POST", "path": "/v1/test", "headers": []})
    exc = RequestValidationError(
        [
            {
                "loc": ("body", "window_hours"),
                "msg": "Input should be greater than or equal to 24",
                "type": "greater_than_equal",
            }
        ]
    )

    response = await _validation_error_handler(request, exc)

    assert response.status_code == 422
    payload = response.body.decode("utf-8")
    assert '"error":"validation_error"' in payload
    assert '"field_errors"' in payload


@pytest.mark.asyncio
async def test_http_exception_handler_normalizes_payload() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/v1/test", "headers": []})
    exc = HTTPException(
        status_code=409,
        detail={
            "error": "analysis_job_conflict",
            "message": "Active job exists",
            "detail": {"blocking_job": {"id": "x"}},
        },
    )

    response = await _unhandled_exception_handler(request, exc)

    assert response.status_code == 409
    payload = response.body.decode("utf-8")
    assert '"error":"analysis_job_conflict"' in payload
    assert '"field_errors":null' in payload
