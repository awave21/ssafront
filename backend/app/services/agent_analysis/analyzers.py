from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import UsageLimits

from app.core.config import get_settings
from app.schemas.agent_analysis import AnalyzerOutput
from app.services.agent_analysis.contracts import (
    AnalyzerBatchOutput,
    AnalyzerDialogContext,
    AnalyzerDialogToolEvent,
    AnalyzerDialogTurn,
)
from app.services.agent_analysis.data_collector import AnalysisDialogSample
from app.services.runtime.model_resolver import resolve_model

ANALYZER_VERSION = "agent-analysis-v1"

_SYSTEM_PROMPT = """\
You are a production QA analyst for conversational agents.

Goal:
- Analyze a batch of dialogs with tool events.
- Discover universal user themes (topics/intents) without assuming a niche.
- Produce actionable recommendations for:
  1) system_prompt
  2) tool_needed
  3) tool_description_fix
  4) knowledge_or_script_gap

Rules:
- Base each recommendation on evidence from dialog IDs.
- Be concise, practical and implementation-focused.
- Never output secrets. Keep excerpts sanitized.
- Recommendations must be reviewable by humans (no auto-apply language).
- Output language policy:
  - Always write human-readable fields in Russian.
  - This applies to summary, topic names, recommendation title/reasoning/suggestion/impact,
    and evidence excerpts.
  - Keep only technical enum/category values as-is:
    system_prompt, tool_needed, tool_description_fix, knowledge_or_script_gap,
    high, medium, low.
"""


@dataclass
class AnalyzerRunResult:
    output: AnalyzerOutput
    prompt_tokens: int
    completion_tokens: int
    request_count: int


def _trim(text: str, limit: int = 800) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _build_context_payload(dialogs: list[AnalysisDialogSample]) -> list[AnalyzerDialogContext]:
    payload: list[AnalyzerDialogContext] = []
    for dialog in dialogs:
        turns: list[AnalyzerDialogTurn] = []
        for msg in dialog.messages[-12:]:
            role = msg.role if msg.role in {"user", "agent", "manager", "system"} else "unknown"
            turns.append(AnalyzerDialogTurn(role=role, text=_trim(msg.content, 1200)))

        tool_events: list[AnalyzerDialogToolEvent] = []
        for event in dialog.tool_events[-16:]:
            result_excerpt: str | None = None
            if event.result is not None:
                result_excerpt = _trim(str(event.result), 500)
            tool_events.append(
                AnalyzerDialogToolEvent(
                    event_type=event.event_type,
                    tool_name=event.tool_name,
                    args=event.args,
                    result_excerpt=result_excerpt,
                    error=_trim(event.error, 300) if event.error else None,
                )
            )

        payload.append(
            AnalyzerDialogContext(
                dialog_id=dialog.session_id,
                dominant_language=dialog.dominant_language,
                has_manager_intervention=dialog.has_manager_intervention,
                turns=turns,
                tool_events=tool_events,
            )
        )
    return payload


def _build_user_prompt(contexts: list[AnalyzerDialogContext]) -> str:
    lines: list[str] = []
    lines.append("Analyze the dialogs and return structured output in Russian.")
    lines.append("Dialogs:")
    for item in contexts:
        lines.append(
            f"- dialog_id={item.dialog_id} lang={item.dominant_language} manager={item.has_manager_intervention}"
        )
        for turn in item.turns:
            lines.append(f"  {turn.role}: {turn.text}")
        for tool_event in item.tool_events:
            lines.append(
                "  tool_event: "
                f"type={tool_event.event_type} "
                f"tool={tool_event.tool_name} "
                f"error={tool_event.error or '-'} "
                f"args={tool_event.args or {}}"
            )
    return "\n".join(lines)


async def analyze_dialog_samples(
    dialogs: list[AnalysisDialogSample],
    *,
    model_name: str | None = None,
    openai_api_key: str | None = None,
    max_llm_requests: int = 20,
) -> AnalyzerRunResult:
    if not dialogs:
        return AnalyzerRunResult(
            output=AnalyzerOutput(summary="Недостаточно данных для анализа.", topics=[], recommendations=[]),
            prompt_tokens=0,
            completion_tokens=0,
            request_count=0,
        )

    settings = get_settings()
    effective_model = model_name or settings.pydanticai_default_model
    model = resolve_model(effective_model, openai_api_key=openai_api_key)

    analyst = PydanticAgent(
        model,
        output_type=AnalyzerBatchOutput,
        system_prompt=_SYSTEM_PROMPT,
    )

    @analyst.output_validator
    def validate_output(_ctx: RunContext[None], output: AnalyzerBatchOutput) -> AnalyzerBatchOutput:
        if not output.summary.strip():
            raise ModelRetry("Summary must be non-empty.")
        cleaned_recs = []
        for rec in output.recommendations:
            if not rec.evidence_dialog_ids:
                raise ModelRetry(
                    f"Recommendation '{rec.title}' must reference at least one evidence dialog id."
                )
            cleaned_recs.append(rec)
        output.recommendations = cleaned_recs[:25]
        output.topics = output.topics[:20]
        return output

    contexts = _build_context_payload(dialogs)
    prompt = _build_user_prompt(contexts)

    result = await analyst.run(
        prompt,
        usage_limits=UsageLimits(
            request_limit=max_llm_requests,
            tool_calls_limit=1,
        ),
    )
    output = result.output if hasattr(result, "output") else result.data

    usage_obj = result.usage() if hasattr(result, "usage") and callable(result.usage) else None
    prompt_tokens = int(getattr(usage_obj, "input_tokens", 0) or 0)
    completion_tokens = int(getattr(usage_obj, "output_tokens", 0) or 0)
    request_count = int(getattr(usage_obj, "requests", 1) or 1)

    return AnalyzerRunResult(
        output=AnalyzerOutput(
            summary=output.summary,
            topics=[topic.model_dump(mode="json") for topic in output.topics],
            recommendations=[rec.model_dump(mode="json") for rec in output.recommendations],
        ),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        request_count=request_count,
    )
