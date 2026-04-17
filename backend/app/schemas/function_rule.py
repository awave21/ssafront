from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ConditionType = Literal[
    "keyword",
    "regex",
    "semantic",
    "json_context",
    "always",
    "schedule_time",
    "schedule_weekday",
    "dialog_source",
    "start_param",
    "after_scenario",
    "client_return_gap",
]
TriggerMode = Literal[
    "pre_run",
    "post_tool",
    "post_run",
    "dialog_start",
    "client_message",
    "agent_message",
    "manager_message",
    "client_return",
    "spend_limit",
    "send_error",
]
ReactionMode = Literal["send_message", "ai_instruction", "ai_self_reply", "silent"]
BehaviorMode = Literal["continue", "pause", "augment_prompt"]
ActionType = Literal[
    "set_tag",
    "send_message",
    "webhook",
    "pause_dialog",
    "augment_prompt",
    "set_result",
    "noop",
    "block_user",
    "unblock_user",
    "resume_dialog",
    "send_delayed",
]
ActionStatus = Literal["success", "error", "always"]

REACTION_MODE_ALIASES: dict[str, ReactionMode] = {
    "send_message": "send_message",
    "ai_instruction": "ai_instruction",
    "ai_self_reply": "ai_self_reply",
    "silent": "silent",
    "Отправить сообщение": "send_message",
    "Инструкция для AI": "ai_instruction",
    "Позволить AI ответить самому": "ai_self_reply",
    "Промолчать": "silent",
}


def _normalize_reaction_mode(value: Any) -> Any:
    if value is None:
        return None
    if not isinstance(value, str):
        return value
    normalized = REACTION_MODE_ALIASES.get(value.strip())
    if normalized is None:
        return value
    return normalized


class FunctionPostActionBase(BaseModel):
    action_type: ActionType
    action_config: dict[str, Any] = Field(default_factory=dict)
    on_status: ActionStatus = "always"
    order_index: int = 0
    enabled: bool = True


class FunctionPostActionCreate(FunctionPostActionBase):
    pass


class FunctionPostActionUpdate(BaseModel):
    action_type: ActionType | None = None
    action_config: dict[str, Any] | None = None
    on_status: ActionStatus | None = None
    order_index: int | None = None
    enabled: bool | None = None


class FunctionPostActionRead(FunctionPostActionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    rule_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class FunctionRuleBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    dry_run: bool = False
    stop_on_match: bool = False
    allow_semantic: bool = True
    priority: int = 100
    trigger_mode: TriggerMode = "pre_run"
    condition_type: ConditionType = "keyword"
    condition_config: dict[str, Any] = Field(default_factory=dict)
    tool_id: UUID | None = None
    reaction_to_execution: ReactionMode = "ai_self_reply"
    behavior_after_execution: BehaviorMode = "continue"

    @field_validator("condition_config")
    @classmethod
    def validate_condition_config(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("condition_config must be object")
        return value

    @field_validator("reaction_to_execution", mode="before")
    @classmethod
    def normalize_reaction_to_execution(cls, value: Any) -> Any:
        return _normalize_reaction_mode(value)


class FunctionRuleCreate(FunctionRuleBase):
    actions: list[FunctionPostActionCreate] = Field(default_factory=list)


class FunctionRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    dry_run: bool | None = None
    stop_on_match: bool | None = None
    allow_semantic: bool | None = None
    priority: int | None = None
    trigger_mode: TriggerMode | None = None
    condition_type: ConditionType | None = None
    condition_config: dict[str, Any] | None = None
    tool_id: UUID | None = None
    reaction_to_execution: ReactionMode | None = None
    behavior_after_execution: BehaviorMode | None = None
    actions: list[FunctionPostActionCreate] | None = None

    @field_validator("reaction_to_execution", mode="before")
    @classmethod
    def normalize_reaction_to_execution(cls, value: Any) -> Any:
        return _normalize_reaction_mode(value)


class FunctionRuleRead(FunctionRuleBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    actions: list[FunctionPostActionRead] = Field(default_factory=list)


class RuleTestRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = Field(min_length=1, max_length=200)
    historical_messages: list[str] = Field(default_factory=list)
    run_tool_calls: bool = False
    trace_id: str | None = None


class RuleActionExecutionTrace(BaseModel):
    action_id: UUID | None = None
    action_type: str
    status: str
    details: dict[str, Any] = Field(default_factory=dict)


class RuleExecutionTrace(BaseModel):
    rule_id: UUID
    matched: bool
    reason: str | None = None
    score: float | None = None
    actions: list[RuleActionExecutionTrace] = Field(default_factory=list)


class RuleTestResponse(BaseModel):
    trace_id: str
    matched_rules: list[RuleExecutionTrace] = Field(default_factory=list)
    tags_created: list[str] = Field(default_factory=list)
    should_pause: bool = False


class DialogTagRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    session_id: str
    tag: str
    source: str
    confidence: float | None = None
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="tag_metadata")
    created_at: datetime
    updated_at: datetime | None = None


class RuleKillSwitchResponse(BaseModel):
    disabled_rules_count: int


class RuleApprovalRead(BaseModel):
    id: UUID
    rule_id: UUID
    run_id: UUID | None = None
    session_id: str
    trace_id: str
    approval_status: Literal["pending_approval", "approved", "denied", "expired"]
    approval_metadata: dict[str, Any] | None = None
    created_at: datetime


class RuleApprovalDecisionRequest(BaseModel):
    decision: Literal["approved", "denied", "expired"]
    metadata: dict[str, Any] | None = None
