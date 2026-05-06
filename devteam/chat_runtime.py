"""Логика запуска агентов через Claude Agent SDK."""
from __future__ import annotations

import logging
from typing import Callable, Awaitable

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
from claude_agent_sdk import AssistantMessage, UserMessage, ResultMessage
from claude_agent_sdk import TextBlock, ToolUseBlock, ToolResultBlock

from devteam.agents.personas import PERSONAS, Persona
from devteam.agents.orchestrator import Orchestrator, Decision
from devteam.config import config
import devteam.storage as storage

log = logging.getLogger(__name__)

# Псевдоним типа для WS-колбэка
BroadcastFn = Callable[[int, dict], Awaitable[None]]

# Максимум раундов оркестровки в групповом чате
MAX_GROUP_ROUNDS = 3

def _build_system_prompt(persona: Persona) -> str:
    voice_block = ""
    if persona.voice:
        examples = "\n".join(f'  - "{v}"' for v in persona.voice)
        voice_block = f"\nПримеры твоих типичных реплик (пиши в таком же тоне, не копируй дословно):\n{examples}\n"

    return f"""Ты {persona.name} ({persona.title}) в командном чате разработки ChatMedBot — \
многотенантной AI-платформы для медицинских клиник. Пишешь как живой коллега в рабочем чате, \
не как корпоративный бот и не как техническая документация.

Характер: {persona.character}
Специализация: {persona.expertise}
{voice_block}
Стек проекта:
- Backend: FastAPI + Python 3.12 + SQLAlchemy + PostgreSQL + PydanticAI
- Frontend: Nuxt 3 + Vue 3 + TypeScript + Tailwind + shadcn-vue
- Инфра: Docker Compose + Caddy

Правила работы:
- Сначала читай существующий код, потом изменяй — не пиши с нуля то что уже есть
- Работай инкрементально: маленькие проверяемые шаги
- Для задач с 3+ шагами — используй TodoWrite в начале работы, обновляй статусы по ходу
- Пиши как коллега в чат: живо, по делу, без формальщины
- Если ответ > 8 строк текста — сожми, оставь главное
- Отвечай на русском языке

В КОНЦЕ каждого ответа где ты что-то делал (читал файлы, менял код) добавь блок:

**Итог:**
- изменено: [список файлов которые писал/редактировал, или «—»]
- прочитано: [список файлов которые читал для анализа, или «—»]
- проверить: [что пользователю стоит проверить руками, 1-2 пункта]

— {persona.emoji} {persona.name}

Если это просто вопрос-ответ без работы с файлами — блок «Итог» пропусти, \
просто подпишись «— {persona.emoji} {persona.name}»."""


def _guard_bash(tool_name: str, tool_input: dict) -> bool:
    """Возвращает True если инструмент разрешён, False если заблокирован."""
    if tool_name != "Bash":
        return True
    cmd = str(tool_input.get("command", ""))
    for pattern in config.bash_deny_patterns:
        if pattern in cmd:
            log.warning("Bash заблокирован: паттерн '%s' в команде: %s", pattern, cmd[:120])
            return False
    return True


async def run_specialist(
    role: str,
    prompt: str,
    chat_id: int,
    broadcast: BroadcastFn,
    session_id: str | None = None,
) -> tuple[str, str | None]:
    """
    Запускает специалиста через ClaudeSDKClient.
    Возвращает (final_text, new_session_id).
    Бродкастит tool_call / tool_result / agent_chunk в WS.
    """
    persona = PERSONAS[role]
    opts = ClaudeAgentOptions(
        system_prompt=_build_system_prompt(persona),
        model=config.model,
        cwd=config.default_cwd,
        allowed_tools=["Read", "Write", "Edit", "Grep", "Glob", "Bash", "TodoWrite"],
        permission_mode="acceptEdits",
        can_use_tool=_guard_bash,
        max_turns=config.max_turns_per_run,
        resume=session_id,
        cli_path=config.cli_path,
    )

    final_text = ""
    new_session_id: str | None = None
    tool_calls_buf: list[dict] = []

    await broadcast(chat_id, {"type": "agent_typing", "role": role})

    try:
        async with ClaudeSDKClient(options=opts) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, TextBlock):
                            final_text += block.text
                            await broadcast(chat_id, {
                                "type": "agent_chunk",
                                "role": role,
                                "delta": block.text,
                            })
                        elif isinstance(block, ToolUseBlock):
                            entry = {"name": block.name, "input": block.input, "output": None}
                            tool_calls_buf.append(entry)
                            await broadcast(chat_id, {
                                "type": "tool_call",
                                "role": role,
                                "tool": block.name,
                                "input": block.input,
                            })

                elif isinstance(msg, UserMessage):
                    for block in msg.content:
                        if isinstance(block, ToolResultBlock):
                            # Сопоставляем с последним незакрытым tool_call
                            output = block.content if isinstance(block.content, str) else str(block.content)
                            for tc in reversed(tool_calls_buf):
                                if tc["output"] is None:
                                    tc["output"] = output
                                    break
                            await broadcast(chat_id, {
                                "type": "tool_result",
                                "role": role,
                                "tool": getattr(block, "tool_use_id", None),
                                "output": output,
                            })

                elif isinstance(msg, ResultMessage):
                    new_session_id = msg.session_id

    except Exception as exc:
        log.exception("Ошибка при запуске агента %s", role)
        await broadcast(chat_id, {"type": "error", "message": str(exc)})
        return "", new_session_id

    # Сохраняем финальное сообщение в БД
    msg_row = storage.create_message(
        chat_id=chat_id,
        author=role,
        content=final_text or f"{persona.emoji} {persona.name} завершил работу.",
        tool_calls=tool_calls_buf if tool_calls_buf else None,
    )
    await broadcast(chat_id, {"type": "message_created", "message": msg_row})

    return final_text, new_session_id


def _build_reply_prefix(reply_to_msg: dict, personas: dict) -> str:
    """Формирует строку-цитату для контекста агента."""
    author = reply_to_msg.get("author", "")
    content = reply_to_msg.get("content", "")[:120]
    persona = personas.get(author)
    if persona:
        label = f"{persona.emoji} {persona.name}"
    elif author == "user":
        label = "пользователь"
    else:
        label = author
    return f'[В ответ на сообщение {label}: «{content}»]\n\n'


async def run_dm_specialist(
    chat_id: int,
    user_message_id: int,
    prompt: str,
    broadcast: BroadcastFn,
    reply_to_msg: dict | None = None,
) -> None:
    """Обрабатывает DM с конкретным специалистом."""
    chat = storage.get_chat(chat_id)
    role = chat["agents"][0]
    session_id = chat.get("session_id")

    full_prompt = prompt
    if reply_to_msg:
        full_prompt = _build_reply_prefix(reply_to_msg, PERSONAS) + prompt

    _, new_session_id = await run_specialist(
        role=role,
        prompt=full_prompt,
        chat_id=chat_id,
        broadcast=broadcast,
        session_id=session_id,
    )

    if new_session_id:
        storage.update_chat(chat_id, session_id=new_session_id)


async def run_dm_orchestrator(
    chat_id: int,
    prompt: str,
    broadcast: BroadcastFn,
    orchestrator: Orchestrator,
) -> None:
    """Обрабатывает DM с оркестратором Максом."""
    # Показываем что Макс думает пока анализирует задачу
    await broadcast(chat_id, {"type": "agent_typing", "role": "orchestrator"})

    decision: Decision = await orchestrator.analyze_async(chat_id, prompt)

    if decision.action == "clarify":
        question = decision.question or "Можете уточнить задачу?"
        msg_row = storage.create_message(chat_id=chat_id, author="orchestrator", content=f"🧠 Макс: {question}")
        await broadcast(chat_id, {"type": "message_created", "message": msg_row})
        return

    # delegate — создаём задачу
    task_row = storage.create_task(
        chat_id=chat_id,
        description=decision.task_for_agents or prompt,
        priority=decision.priority or "🟢 Обычно",
        agent_roles=decision.agents,
    )

    # Сообщение от Макса с планом делегирования
    agents_list = ", ".join(decision.agents)
    summary_text = (
        f"🧠 Макс: {decision.summary}\n\n"
        f"**Приоритет:** {decision.priority}  "
        f"**Исполнители:** {agents_list}\n\n"
        f"Передаю задачу команде:\n> {decision.task_for_agents}"
    )
    msg_row = storage.create_message(
        chat_id=chat_id,
        author="orchestrator",
        content=summary_text,
        task_id=task_row["id"],
    )
    await broadcast(chat_id, {"type": "message_created", "message": msg_row})
    await broadcast(chat_id, {"type": "task_status", "task": task_row})

    storage.update_task(task_row["id"], status="in_progress")

    # Запускаем специалистов последовательно — каждый пишет в чат сам
    task_prompt = decision.task_for_agents or prompt
    for role in decision.agents:
        await run_specialist(
            role=role,
            prompt=task_prompt,
            chat_id=chat_id,
            broadcast=broadcast,
        )

    storage.update_task(task_row["id"], status="done")
    done_task = storage.get_task(task_row["id"])
    await broadcast(chat_id, {"type": "task_status", "task": done_task})

    # Макс подводит итог
    await broadcast(chat_id, {"type": "agent_typing", "role": "orchestrator"})
    done_msg = storage.create_message(
        chat_id=chat_id,
        author="orchestrator",
        content=f"🧠 Макс: Задача выполнена командой ({agents_list}). Проверяйте результаты выше.",
        task_id=task_row["id"],
    )
    await broadcast(chat_id, {"type": "message_created", "message": done_msg})


async def run_group_message(
    chat_id: int,
    prompt: str,
    broadcast: BroadcastFn,
    orchestrator: Orchestrator,
    reply_to_msg: dict | None = None,
) -> None:
    """
    Обрабатывает сообщение в групповом чате.
    Поддерживает @role для прямого обращения к специалисту.
    По умолчанию идёт через оркестратора, который может
    подключить специалистов (до MAX_GROUP_ROUNDS раундов).
    """
    # Контекст цитаты (одинаков для всех путей)
    reply_prefix = _build_reply_prefix(reply_to_msg, PERSONAS) if reply_to_msg else ""

    # Проверяем @mention
    addressed_role = _extract_mention(prompt)

    if addressed_role and addressed_role in PERSONAS and addressed_role != "orchestrator":
        cleaned = _strip_mention(prompt)
        await run_specialist(
            role=addressed_role,
            prompt=reply_prefix + cleaned,
            chat_id=chat_id,
            broadcast=broadcast,
        )
        return

    # Без @mention — Макс решает что делать
    await broadcast(chat_id, {"type": "agent_typing", "role": "orchestrator"})
    decision: Decision = await orchestrator.analyze_async(chat_id, prompt)

    if decision.action == "clarify":
        # Макс уточняет у пользователя перед задачей
        question = decision.question or "Можете уточнить?"
        msg_row = storage.create_message(chat_id=chat_id, author="orchestrator", content=f"🧠 Макс: {question}")
        await broadcast(chat_id, {"type": "message_created", "message": msg_row})
        return

    if decision.action == "discuss":
        # Обычное общение — Макс приглашает нужных специалистов ответить
        topic = decision.topic or prompt
        for role in (decision.agents or list(PERSONAS.keys())[1:]):
            if role == "orchestrator":
                continue
            persona = PERSONAS.get(role)
            if not persona:
                continue
            voice_hint = ""
            if persona.voice:
                voice_hint = f"\nТвой стиль общения (пример реплик): {'; '.join(persona.voice[:2])}\n"
            discuss_prompt = (
                f"В командном чате идёт обсуждение: «{topic}»\n"
                f"Сообщение: {prompt}\n"
                f"{voice_hint}\n"
                f"Ты — {persona.name} ({persona.title}). Характер: {persona.character}\n\n"
                f"Ответь как живой коллега в рабочем чате — своё мнение, свой угол зрения. "
                f"Начни с реакции на тему (не с приветствия). "
                f"Строго 2-4 предложения, не больше. Без формальщины. "
                f"Подпиши: — {persona.emoji} {persona.name}"
            )
            await run_specialist(
                role=role,
                prompt=discuss_prompt,
                chat_id=chat_id,
                broadcast=broadcast,
            )
        return

    # delegate — Макс ставит задачу и координирует
    for _round in range(MAX_GROUP_ROUNDS):
        agents_list = ", ".join(decision.agents)
        summary_text = (
            f"🧠 Макс: {decision.summary}\n"
            f"Ставлю задачу: {agents_list}"
        )
        msg_row = storage.create_message(chat_id=chat_id, author="orchestrator", content=summary_text)
        await broadcast(chat_id, {"type": "message_created", "message": msg_row})

        if not decision.agents:
            break

        task_prompt = decision.task_for_agents or prompt
        all_results: list[str] = []

        for role in decision.agents:
            result, _ = await run_specialist(
                role=role,
                prompt=task_prompt,
                chat_id=chat_id,
                broadcast=broadcast,
            )
            all_results.append(result)

        # Следующий раунд: нужен ли ещё кто-то
        combined = "\n\n".join(all_results)
        await broadcast(chat_id, {"type": "agent_typing", "role": "orchestrator"})
        decision = await orchestrator.analyze_async(
            chat_id,
            f"Специалисты завершили. Результаты:\n\n{combined}\n\nНужен ли кто-то ещё по исходной задаче?"
        )
        if decision.action != "delegate" or not decision.agents:
            break

    # Финальное резюме от Макса
    await broadcast(chat_id, {"type": "agent_typing", "role": "orchestrator"})
    final_msg = storage.create_message(chat_id=chat_id, author="orchestrator", content="🧠 Макс: Команда завершила работу.")
    await broadcast(chat_id, {"type": "message_created", "message": final_msg})


def _extract_mention(text: str) -> str | None:
    """Извлекает @role из начала сообщения."""
    stripped = text.strip()
    if not stripped.startswith("@"):
        return None
    parts = stripped.split(None, 1)
    return parts[0][1:].lower() if parts else None


def _strip_mention(text: str) -> str:
    """Убирает первое @слово из сообщения."""
    parts = text.strip().split(None, 1)
    return parts[1] if len(parts) > 1 else ""
