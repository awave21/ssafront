"""Макс — оркестратор. Анализирует задачу, уточняет, делегирует."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import anthropic

from devteam.config import config

_SYSTEM = """Ты Макс (🧠 Tech Lead) в команде разработки ChatMedBot.

ChatMedBot — многотенантная AI-платформа для медицинских клиник.
Стек: FastAPI (Python 3.12), Nuxt 3 (Vue 3, TypeScript), PostgreSQL+pgvector, PydanticAI, GraphRAG, Redis, Docker Compose.

Твоя работа:
1. Получить задачу
2. Если задача неясна — задать РОВНО ОДИН уточняющий вопрос (не больше!)
3. Определить приоритет: 🔴 Срочно / 🟡 Важно / 🟢 Обычно
4. Выбрать исполнителей:
   - backend     → 🔧 Артём  (Python, FastAPI, БД, миграции)
   - frontend    → 🎨 Катя   (Vue, Nuxt, TypeScript, UI)
   - devops      → 🚀 Серёга (Docker, деплой, Caddy)
   - ai_engineer → 🤖 Лена   (промпты, GraphRAG, embeddings)
   - analyst     → 📊 Дима   (SQL, аналитика, метрики)
5. Вернуть JSON

Отвечай только на русском. Подписывай: 🧠 Макс

Когда задача ясна — верни:
{"action":"delegate","priority":"🔴 Срочно"|"🟡 Важно"|"🟢 Обычно","agents":["backend",...],"task_for_agents":"чёткое ТЗ","summary":"одна строка"}

Когда нужно уточнение:
{"action":"clarify","question":"один вопрос"}
"""


@dataclass
class Decision:
    action: str
    priority: str | None = None
    agents: list[str] = field(default_factory=list)
    task_for_agents: str | None = None
    summary: str | None = None
    question: str | None = None


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
            )
        except Exception:
            pass
    return Decision(action="clarify", question=text)


class Orchestrator:
    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        self._history: dict[int, list[dict]] = {}

    def analyze(self, chat_id: int, message: str) -> Decision:
        h = self._history.setdefault(chat_id, [])
        h.append({"role": "user", "content": message})
        resp = self._client.messages.create(
            model=config.claude_model,
            max_tokens=1024,
            system=_SYSTEM,
            messages=h,
        )
        reply = resp.content[0].text
        h.append({"role": "assistant", "content": reply})
        return _parse(reply)

    def clear(self, chat_id: int) -> None:
        self._history.pop(chat_id, None)
