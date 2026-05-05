"""
DevTeam Telegram Bot — Макс + 5 специалистов.

Флоу:
  Пользователь → @МаксBot → уточнение? → план + подтверждение
  → специалисты пишут прогресс в группу от своих ботов
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from devteam.config import config
from devteam.task_manager import Priority, Status, create_task, list_tasks, update_task
from devteam.agents.personas import PERSONAS
from devteam.agents.orchestrator import Decision, Orchestrator
from devteam.agents.base import SpecialistAgent

logger = logging.getLogger(__name__)

main_bot = Bot(token=config.telegram_bot_token)
dp = Dispatcher()
orchestrator = Orchestrator()

# chat_id → "idle" | "clarifying" | "confirming:<task_id>"
_states: dict[int, str] = {}
# task_id → Decision
_pending: dict[int, Decision] = {}


# ── Posting helpers ──────────────────────────────────────────────

async def post_specialist(role: str, text: str) -> None:
    """Специалист пишет в группу от своего бота."""
    if not config.group_chat_id:
        return
    token = config.specialist_token(role)
    bot = Bot(token=token)
    try:
        await bot.send_message(config.group_chat_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.warning("post_specialist %s: %s", role, e)
    finally:
        await bot.session.close()


async def post_main(chat_id: int, text: str, **kw) -> None:
    try:
        await main_bot.send_message(chat_id, text, parse_mode="Markdown", **kw)
    except Exception as e:
        logger.warning("post_main: %s", e)


# ── Team intro ───────────────────────────────────────────────────

def _intro() -> str:
    lines = ["👋 *Команда разработки ChatMedBot*\n"]
    for p in PERSONAS.values():
        lines.append(f"{p.emoji} *{p.name}* — {p.title}")
        lines.append(f"   _{p.expertise}_\n")
    lines.append("Напиши задачу — 🧠 Макс разберётся кому передать!")
    return "\n".join(lines)


def _confirm_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Выполнить", callback_data=f"confirm:{task_id}"),
        InlineKeyboardButton(text="❌ Отмена",    callback_data=f"cancel:{task_id}"),
    ]])


# ── Agent runner ─────────────────────────────────────────────────

async def _run_agents(chat_id: int, task_id: int, decision: Decision) -> None:
    update_task(task_id, status=Status.in_progress.value)

    await post_main(chat_id, f"🏁 Задача *#{task_id}* в работе — следи за прогрессом в группе 👇")

    for role in decision.agents:
        persona = PERSONAS.get(role)
        if not persona:
            continue

        await post_specialist(role, f"{persona.emoji} *{persona.name}* берётся за задачу:\n_{decision.summary}_")

        progress_q: asyncio.Queue[str] = asyncio.Queue(maxsize=50)

        def on_update(text: str, _q=progress_q) -> None:
            try:
                _q.put_nowait(text)
            except asyncio.QueueFull:
                pass

        async def flush(_role=role, _p=persona, _q=progress_q) -> None:
            while True:
                try:
                    msg = _q.get_nowait()
                    await post_specialist(_role, f"{_p.emoji} {msg[:800]}")
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0.5)

        try:
            flush_task = asyncio.create_task(flush())
            result = await SpecialistAgent(persona).run(decision.task_for_agents or "", on_update)
            flush_task.cancel()
            await post_specialist(role, f"✅ {persona.emoji} *{persona.name}* завершил:\n\n{result[:1800]}")
        except Exception as e:
            await post_specialist(role, f"❌ {persona.emoji} *{persona.name}*: ошибка — {e}")

    update_task(task_id, status=Status.done.value)
    await post_main(chat_id, f"🧠 *Макс:* Задача *#{task_id}* выполнена ✅")
    if config.group_chat_id:
        await post_main(config.group_chat_id, f"🧠 *Макс:* Задача *#{task_id}* — *{decision.summary}* закрыта ✅")


# ── Handlers ─────────────────────────────────────────────────────

@dp.message(Command("start"))
async def h_start(msg: Message) -> None:
    await msg.answer(_intro(), parse_mode="Markdown")


@dp.message(Command("help"))
async def h_help(msg: Message) -> None:
    await msg.answer(
        "📋 *Как работать*\n\n"
        "• Напиши задачу — Макс разберёт и распределит\n"
        "• Макс задаст максимум один уточняющий вопрос\n"
        "• Покажет план — подтверди кнопкой\n"
        "• Специалисты пишут прогресс в группе\n\n"
        "/tasks — список задач\n"
        "/cancel — отменить текущую задачу",
        parse_mode="Markdown",
    )


@dp.message(Command("tasks"))
async def h_tasks(msg: Message) -> None:
    tasks = list_tasks(msg.chat.id)
    if not tasks:
        await msg.answer("Задач пока нет.")
        return
    icons = {"done": "✅", "in_progress": "⚙️", "pending": "🕐", "failed": "❌"}
    lines = ["📋 *Задачи:*\n"] + [
        f"{icons.get(t['status'], '❓')} #{t['id']} {t['priority']} — {t['description'][:60]}"
        for t in tasks[:10]
    ]
    await msg.answer("\n".join(lines), parse_mode="Markdown")


@dp.message(Command("cancel"))
async def h_cancel(msg: Message) -> None:
    _states[msg.chat.id] = "idle"
    orchestrator.clear(msg.chat.id)
    await msg.answer("🛑 Отменено.")


@dp.message(F.text)
async def h_message(msg: Message) -> None:
    chat_id = msg.chat.id

    allowed = config.get_allowed_chat_ids()
    if allowed and chat_id not in allowed:
        await msg.answer("⛔ Нет доступа.")
        return

    state = _states.get(chat_id, "idle")

    if state == "clarifying":
        thinking = await msg.answer("🧠 *Макс* думает…", parse_mode="Markdown")
        decision = orchestrator.analyze(chat_id, msg.text or "")
        await main_bot.delete_message(chat_id, thinking.message_id)
    else:
        _states[chat_id] = "idle"
        orchestrator.clear(chat_id)
        thinking = await msg.answer("🧠 *Макс* анализирует…", parse_mode="Markdown")
        decision = orchestrator.analyze(chat_id, msg.text or "")
        await main_bot.delete_message(chat_id, thinking.message_id)

    await _handle(msg, decision)


async def _handle(msg: Message, decision: Decision) -> None:
    chat_id = msg.chat.id

    if decision.action == "clarify":
        _states[chat_id] = "clarifying"
        await msg.answer(f"🧠 *Макс:* {decision.question}", parse_mode="Markdown")
        return

    if decision.action == "delegate":
        agents_str = " + ".join(
            f"{PERSONAS[r].emoji} {PERSONAS[r].name}"
            for r in decision.agents if r in PERSONAS
        )
        text = (
            f"🧠 *Макс:* Вот план\n\n"
            f"📌 *Задача:* {decision.summary}\n"
            f"⚡ *Приоритет:* {decision.priority}\n"
            f"👥 *Исполнители:* {agents_str}\n\n"
            f"*ТЗ:*\n_{decision.task_for_agents}_\n\n"
            f"Подтверждаем?"
        )
        pmap = {"🔴 Срочно": Priority.urgent, "🟡 Важно": Priority.high, "🟢 Обычно": Priority.normal}
        task_id = create_task(
            chat_id=chat_id,
            description=decision.summary or "задача",
            priority=pmap.get(decision.priority or "", Priority.normal),
            agent_role=",".join(decision.agents),
            message_id=msg.message_id,
        )
        _pending[task_id] = decision
        _states[chat_id] = f"confirming:{task_id}"
        await msg.answer(text, parse_mode="Markdown", reply_markup=_confirm_kb(task_id))


@dp.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(call: CallbackQuery) -> None:
    task_id = int(call.data.split(":")[1])
    decision = _pending.pop(task_id, None)
    chat_id = call.message.chat.id

    _states[chat_id] = "idle"
    orchestrator.clear(chat_id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("✅ Запущено!")

    if not decision:
        await call.message.answer("⚠️ Задача не найдена, повторите запрос.")
        return

    intro = "\n".join(
        f"{PERSONAS[r].emoji} *{PERSONAS[r].name}* готов"
        for r in decision.agents if r in PERSONAS
    )
    await call.message.answer(f"🚀 *Поехали!*\n\n{intro}\n\nПрогресс — в группе 👇", parse_mode="Markdown")
    asyncio.create_task(_run_agents(chat_id, task_id, decision))


@dp.callback_query(F.data.startswith("cancel:"))
async def cb_cancel(call: CallbackQuery) -> None:
    task_id = int(call.data.split(":")[1])
    _pending.pop(task_id, None)
    update_task(task_id, status=Status.failed.value, result="Отменено пользователем")
    _states[call.message.chat.id] = "idle"
    orchestrator.clear(call.message.chat.id)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer("❌")
    await call.message.answer("🛑 Задача отменена.")
