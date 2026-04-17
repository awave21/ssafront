from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ToolCallStatus = Literal["success", "error", "skipped", "dry_run"]


class ToolCallHistoryParamItem(BaseModel):
    key: str
    value: Any


class ToolCallHistoryAgentRef(BaseModel):
    id: str
    name: str


class ToolCallHistoryItem(BaseModel):
    entry_type: Literal["tool", "scenario"] = "tool"
    id: str
    tool_name: str
    tool_description: str
    tool_settings_url: str
    status: ToolCallStatus
    invoked_at: datetime
    duration_ms: int | None = Field(default=None, ge=0)
    agent: ToolCallHistoryAgentRef
    user_info: dict[str, Any]
    params: list[ToolCallHistoryParamItem] = Field(default_factory=list)
    request_payload: dict[str, Any] | None = None
    response_payload: dict[str, Any] | None = None
    error_payload: dict[str, Any] | None = None
    rule_id: str | None = None
    rule_name: str | None = None
    trigger_phase: str | None = None
    matched: bool | None = None
    rule_result_status: str | None = None
    reason: str | None = None


class ToolCallHistoryResponse(BaseModel):
    items: list[ToolCallHistoryItem] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ToolCallHistoryQuery(BaseModel):
    date_from: date
    date_to: date
    timezone: str = "UTC"
    agent_id: str | None = None
    tool_name: str | None = None
    status: ToolCallStatus | None = None
    search: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
