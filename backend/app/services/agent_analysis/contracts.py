from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AnalyzerDialogTurn(BaseModel):
    role: Literal["user", "agent", "manager", "system", "unknown"]
    text: str = Field(default="", max_length=3000)


class AnalyzerDialogToolEvent(BaseModel):
    event_type: str
    tool_name: str | None = None
    args: dict[str, Any] | None = None
    result_excerpt: str | None = None
    error: str | None = None


class AnalyzerDialogContext(BaseModel):
    dialog_id: str
    dominant_language: str = "unknown"
    has_manager_intervention: bool = False
    turns: list[AnalyzerDialogTurn] = Field(default_factory=list)
    tool_events: list[AnalyzerDialogToolEvent] = Field(default_factory=list)


class AnalyzerTopic(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    dialogs_count: int = Field(..., ge=0)
    share: float = Field(..., ge=0, le=1)
    health: Literal["good", "warning", "critical"] = "warning"
    evidence_dialog_ids: list[str] = Field(
        default_factory=list,
        description="dialog_id из анализируемой выборки, относящиеся к теме (до 15 шт.).",
    )


class AnalyzerRecommendationEvidence(BaseModel):
    dialog_id: str = Field(..., min_length=1)
    run_id: UUID | None = None
    message_id: UUID | None = None
    excerpt: str | None = None


class AnalyzerRecommendation(BaseModel):
    category: Literal[
        "system_prompt",
        "tool_needed",
        "tool_description_fix",
        "knowledge_or_script_gap",
    ]
    priority: Literal["high", "medium", "low"]
    confidence: float = Field(..., ge=0, le=1)
    title: str = Field(..., min_length=3, max_length=300)
    reasoning: str = Field(..., min_length=5)
    suggestion: str = Field(..., min_length=5)
    impact: str | None = None
    evidence_dialog_ids: list[str] = Field(default_factory=list)
    evidence: list[AnalyzerRecommendationEvidence] = Field(default_factory=list)


class AnalyzerBatchOutput(BaseModel):
    summary: str = Field(..., min_length=5)
    topics: list[AnalyzerTopic] = Field(default_factory=list)
    recommendations: list[AnalyzerRecommendation] = Field(default_factory=list)
