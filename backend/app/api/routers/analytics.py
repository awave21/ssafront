from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_scope
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.tool_call_history import ToolCallHistoryQuery, ToolCallHistoryResponse
from app.services.tool_call_history import ToolCallHistoryService

router = APIRouter()


@router.get("/tool-calls-history", response_model=ToolCallHistoryResponse)
async def get_tool_calls_history(
    date_from: str = Query(...),
    date_to: str = Query(...),
    timezone: str = Query(default="UTC"),
    agent_id: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    status_value: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    limit: int = Query(default=20),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("analytics:view")),
) -> ToolCallHistoryResponse:
    if user.role not in {"admin", "owner"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"message": "Admin access required", "error": "forbidden"},
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid limit", "error": "invalid_limit"},
        )

    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid offset", "error": "invalid_offset"},
        )

    if status_value not in {None, "success", "error"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Invalid status filter", "error": "invalid_status"},
        )

    try:
        parsed_date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        parsed_date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        query = ToolCallHistoryQuery(
            date_from=parsed_date_from,
            date_to=parsed_date_to,
            timezone=timezone,
            agent_id=agent_id,
            tool_name=tool_name,
            status=status_value,
            search=search,
            limit=limit,
            offset=offset,
        )
        service = ToolCallHistoryService(db)
        return await service.list(tenant_id=user.tenant_id, query=query)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": str(exc), "error": "invalid_params"},
        ) from exc
