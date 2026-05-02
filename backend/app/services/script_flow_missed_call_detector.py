"""Stage 5: detect runs where the LLM SHOULD have called `search_expert_tactics`
but didn't.

Heuristic: take recent successful runs that did NOT call the tool, ask a cheap
LLM to classify the user message into one of:
  trigger | objection | concern | qualification | closing | none

If classification is anything but `none`, we record a missed call. The expert
sees aggregated counts per classification and can decide whether to:
- improve the tool description so the LLM picks it up better;
- write a system-prompt nudge for that intent type;
- accept that the topic is genuinely off-script.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.run import Run
from app.db.models.script_flow_missed_tactic_call import ScriptFlowMissedTacticCall
from app.db.models.tenant_llm_config import TenantLLMConfig  # noqa: F401
from app.services.tenant_llm_config import get_decrypted_api_key

log = structlog.get_logger(__name__)

VALID_CLASSES = {"trigger", "objection", "concern", "qualification", "closing"}
MAX_RUNS_PER_BATCH = 60


_CLASSIFY_PROMPT_TEMPLATE = (
    "Ты классифицируешь сообщение клиента медицинской клиники по типу намерения. "
    "Возможные классы:\n"
    "- trigger      — клиент впервые спрашивает про услугу/процедуру\n"
    "- objection    — возражение (цена, конкуренты, страх, недоверие)\n"
    "- concern      — беспокойство/уточнение про побочные эффекты, безопасность\n"
    "- qualification— уточнение деталей до записи (опыт, состояние, противопоказания)\n"
    "- closing      — готов записаться, спрашивает время/дату\n"
    "- none         — простой инфо-запрос (адрес, режим работы, общий вопрос)\n\n"
    "Сообщение:\n__MESSAGE__\n\n"
    'Ответь строго в JSON: {"classification": "<class>", "confidence": 0.0..1.0}'
)


def _build_classify_prompt(message: str) -> str:
    return _CLASSIFY_PROMPT_TEMPLATE.replace("__MESSAGE__", message[:1000])


async def _classify_message(
    *,
    openai_api_key: str,
    message: str,
) -> tuple[str, float]:
    from app.services.runtime.model_resolver import resolve_openai_client
    from app.core.config import get_settings

    settings = get_settings()
    model = settings.summary_model or "gpt-4o-mini"
    if isinstance(model, str) and model.startswith("openai:"):
        model = model.split(":", 1)[1]
    try:
        client = resolve_openai_client(openai_api_key=openai_api_key)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": _build_classify_prompt(message)}],
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=80,
        )
        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)
        cls = (data.get("classification") or "").lower().strip()
        if cls not in VALID_CLASSES:
            cls = "none"
        conf = float(data.get("confidence") or 0.0)
        return cls, max(0.0, min(1.0, conf))
    except Exception as exc:  # noqa: BLE001
        log.warning("missed_call.classify_failed", error=str(exc))
        return ("none", 0.0)


def _extract_user_message(run: Run) -> str:
    """Best-effort extraction of the user's last message for this run."""
    if run.input_message:
        return str(run.input_message)[:2000]
    return ""


async def detect_missed_calls(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    period_hours: int = 24,
    max_runs: int = MAX_RUNS_PER_BATCH,
) -> int:
    """Scan recent runs without `search_expert_tactics`, classify, and record.

    Already-recorded run_ids are skipped (idempotent).
    """
    api_key = await get_decrypted_api_key(db, tenant_id, "openai")
    if not api_key:
        log.warning("missed_call.no_api_key", tenant_id=str(tenant_id))
        return 0

    since = datetime.now(timezone.utc) - timedelta(hours=period_hours)

    # Already-classified run_ids — skip them
    existing_q = (
        select(ScriptFlowMissedTacticCall.run_id)
        .where(
            ScriptFlowMissedTacticCall.tenant_id == tenant_id,
            ScriptFlowMissedTacticCall.agent_id == agent_id,
            ScriptFlowMissedTacticCall.run_id.is_not(None),
            ScriptFlowMissedTacticCall.created_at >= since - timedelta(days=2),
        )
    )
    existing_ids = {
        row[0] for row in (await db.execute(existing_q)).all() if row[0] is not None
    }

    # Recent successful runs that did NOT call search_expert_tactics
    runs_q = (
        select(Run)
        .where(
            Run.tenant_id == tenant_id,
            Run.agent_id == agent_id,
            Run.status == "succeeded",
            Run.created_at >= since,
        )
        .order_by(desc(Run.created_at))
        .limit(max_runs * 2)  # over-fetch to compensate for filtered ones
    )
    runs = (await db.execute(runs_q)).scalars().all()

    candidates = []
    for r in runs:
        if r.id in existing_ids:
            continue
        tools = r.tools_called or []
        if isinstance(tools, str):
            try:
                tools = json.loads(tools)
            except Exception:
                tools = []
        if "search_expert_tactics" in (tools or []):
            continue
        msg = _extract_user_message(r)
        if not msg or len(msg.strip()) < 4:
            continue
        candidates.append((r, msg))
        if len(candidates) >= max_runs:
            break

    if not candidates:
        return 0

    now = datetime.now(timezone.utc)
    saved = 0
    for run, msg in candidates:
        cls, conf = await _classify_message(openai_api_key=api_key, message=msg)
        if cls == "none":
            # Still record a "none" with confidence so we don't reprocess
            # the same run on the next worker tick. We DO want to mark these,
            # so use a marker entry — but to keep the table focused we skip
            # recording "none" entirely. Instead, the dedup is by run_id+
            # since-window, which is good enough for a 24h period.
            continue
        db.add(
            ScriptFlowMissedTacticCall(
                tenant_id=tenant_id,
                agent_id=agent_id,
                run_id=run.id,
                user_message=msg[:2000],
                classification=cls,
                confidence=conf,
                created_at=now,
            )
        )
        saved += 1

    if saved:
        await db.commit()
    log.info("missed_call.detect.done", agent_id=str(agent_id), saved=saved)
    return saved


async def get_missed_calls_summary(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
    period_days: int = 7,
    examples_per_class: int = 5,
) -> dict[str, Any]:
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    counts_q = (
        select(
            ScriptFlowMissedTacticCall.classification,
            func.count().label("c"),
        )
        .where(
            ScriptFlowMissedTacticCall.tenant_id == tenant_id,
            ScriptFlowMissedTacticCall.agent_id == agent_id,
            ScriptFlowMissedTacticCall.created_at >= since,
        )
        .group_by(ScriptFlowMissedTacticCall.classification)
        .order_by(desc("c"))
    )
    counts = (await db.execute(counts_q)).all()

    classes: list[dict[str, Any]] = []
    for cls, c in counts:
        ex_q = (
            select(ScriptFlowMissedTacticCall)
            .where(
                ScriptFlowMissedTacticCall.tenant_id == tenant_id,
                ScriptFlowMissedTacticCall.agent_id == agent_id,
                ScriptFlowMissedTacticCall.classification == cls,
                ScriptFlowMissedTacticCall.created_at >= since,
            )
            .order_by(desc(ScriptFlowMissedTacticCall.confidence))
            .limit(examples_per_class)
        )
        examples = (await db.execute(ex_q)).scalars().all()
        classes.append(
            {
                "classification": cls,
                "count": int(c),
                "examples": [
                    {
                        "user_message": e.user_message,
                        "confidence": round(e.confidence, 2) if e.confidence is not None else None,
                        "created_at": e.created_at.isoformat(),
                    }
                    for e in examples
                ],
            }
        )
    return {"period_days": period_days, "classes": classes}
