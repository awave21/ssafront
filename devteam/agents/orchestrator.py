"""Макс — оркестратор. Анализирует задачу, уточняет, делегирует."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anyio
from claude_agent_sdk import query as sdk_query, ClaudeAgentOptions
from claude_agent_sdk import AssistantMessage, TextBlock

from devteam.config import config
import devteam.storage as storage

_SYSTEM = """Ты Макс (🧠 Tech Lead) — спокойный, системный лидер команды разработки ChatMedBot.

ChatMedBot — многотенантная AI-платформа для медицинских клиник.
Стек: FastAPI (Python 3.12), Nuxt 3 (Vue 3, TypeScript), PostgreSQL+pgvector, PydanticAI, GraphRAG, Redis, Docker Compose.

Команда:
- backend     → 🔧 Артём  (Python, FastAPI, БД, миграции)
- frontend    → 🎨 Катя   (Vue, Nuxt, TypeScript, UI)
- devops      → 🚀 Серёга (Docker, деплой, Caddy)
- ai_engineer → 🤖 Лена   (промпты, GraphRAG, embeddings)
- analyst     → 📊 Дима   (SQL, аналитика, метрики)

Твой стиль: режешь скоуп до минимума, объясняешь почему именно эти исполнители, \
задаёшь максимум один уточняющий вопрос. Пишешь как живой тимлид в рабочем чате — \
кратко и по делу, без корпоративных клише. В полях summary/question/topic — живые фразы, не канцелярит.

Правила:
1. Это живой командный чат — общение свободное.
2. Вопрос, обсуждение, идея, «а что если» → "discuss" (специалисты отвечают от себя).
3. Задача с изменением кода/системы → сначала "clarify" (один вопрос), потом "delegate".
4. Ты КООРДИНИРУЕШЬ, не пишешь код сам. Задачи раздаёшь только ты.

Верни ОДИН JSON-объект:

Обсуждение/вопрос (пусть специалисты выскажутся):
{"action":"discuss","agents":["backend","frontend",...],"topic":"краткое резюме для специалистов"}

Нужно уточнение (один вопрос, не больше):
{"action":"clarify","question":"конкретный уточняющий вопрос своим голосом"}

Готово делегировать:
{"action":"delegate","priority":"🔴 Срочно"|"🟡 Важно"|"🟢 Обычно","agents":["backend",...],"task_for_agents":"чёткое ТЗ что сделать","summary":"одна строка своим голосом"}
"""


@dataclass
class Decision:
    action: str                          # "discuss" | "clarify" | "delegate"
    priority: str | None = None
    agents: list[str] = field(default_factory=list)
    task_for_agents: str | None = None
    summary: str | None = None
    question: str | None = None
    topic: str | None = None             # для discuss — что обсуждаем


def _parse(text: str) -> Decision:
    m = re.search(r"\{[\s\S]+\}", text)
    if m:
        try:
            d = json.loads(m.group())
            return Decision(
                action=d.get("action", "clarify"),
                priority=d.get("priority"),
                agents=d.get("agents", []),
                task_for_agents=d.get("task_for_agents"),
                summary=d.get("summary"),
                question=d.get("question"),
                topic=d.get("topic"),
            )
        except Exception:
            pass
    return Decision(action="clarify", question=text)


async def _analyze_async(history: list[dict], message: str) -> Decision:
    """Отправляет сообщение Максу через Claude Agent SDK и возвращает Decision."""
    context_parts = []
    for h in history:
        role = h.get("role", "user")
        label = h.get("label", "Пользователь" if role == "user" else "Макс")
        context_parts.append(f"{label}: {h['content']}")
    context_parts.append(f"Пользователь: {message}")
    prompt = "\n\n".join(context_parts)

    opts = ClaudeAgentOptions(
        system_prompt=_SYSTEM,
        model=config.model,
        max_turns=1,
        allowed_tools=[],       # оркестратор не использует tools
        cli_path=config.cli_path,
    )

    reply = ""
    async for msg in sdk_query(prompt=prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    reply += block.text

    return _parse(reply), reply


class Orchestrator:
    def __init__(self) -> None:
        # История диалога per chat_id (in-memory, теряется при рестарте — нормально для MVP)
        self._history: dict[int, list[dict]] = {}

    def analyze(self, chat_id: int, message: str) -> Decision:
        """Синхронная обёртка для вызова из asyncio.to_thread."""
        h = self._history.setdefault(chat_id, [])
        decision, reply = anyio.from_thread.run_sync(
            lambda: anyio.run(_analyze_async, h, message)
        ) if False else self._run_sync(h, message)
        h.append({"role": "user", "content": message})
        h.append({"role": "assistant", "content": reply})
        return decision

    def _run_sync(self, history: list[dict], message: str) -> tuple[Decision, str]:
        """Запускает async analyze в синхронном контексте."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(_analyze_async(history, message))

    async def analyze_async(self, chat_id: int, message: str) -> Decision:
        """Async version: строит контекст из БД — Макс всегда видит историю чата."""
        from devteam.agents.personas import PERSONAS as _PERSONAS

        db_msgs = storage.list_messages(chat_id, limit=40)
        h: list[dict] = []
        for m in db_msgs[-25:]:
            author = m["author"]
            content = (m["content"] or "")[:600]
            if author == "user":
                h.append({"role": "user", "label": "Пользователь", "content": content})
            elif author == "orchestrator":
                h.append({"role": "assistant", "label": "Макс", "content": content})
            else:
                persona = _PERSONAS.get(author)
                name = f"{persona.emoji} {persona.name}" if persona else author
                h.append({"role": "assistant", "label": name, "content": content})

        decision, _ = await _analyze_async(h, message)
        return decision

    def clear(self, chat_id: int) -> None:
        self._history.pop(chat_id, None)
