"""FastAPI-приложение devteam: REST + WebSocket."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from devteam.agents.orchestrator import Orchestrator
from devteam.agents.personas import PERSONAS
from devteam.config import config
import devteam.storage as storage
from devteam.chat_runtime import (
    run_dm_specialist,
    run_dm_orchestrator,
    run_group_message,
)

log = logging.getLogger(__name__)

app = FastAPI(title="DevTeam API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Синглтон оркестратора (хранит in-memory историю диалогов)
_orchestrator = Orchestrator()


# ─── Auth ─────────────────────────────────────────────────────────────────────

def check_token(authorization: str = Header(...)) -> None:
    token = authorization.removeprefix("Bearer ").strip()
    if token != config.api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}

    async def connect(self, chat_id: int, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(chat_id, set()).add(ws)

    def disconnect(self, chat_id: int, ws: WebSocket) -> None:
        conns = self._connections.get(chat_id, set())
        conns.discard(ws)

    async def broadcast(self, chat_id: int, data: dict) -> None:
        conns = self._connections.get(chat_id, set())
        dead: set[WebSocket] = set()
        for ws in list(conns):
            try:
                await ws.send_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                dead.add(ws)
        conns -= dead


manager = ConnectionManager()


# ─── Pydantic schemas ─────────────────────────────────────────────────────────

class CreateChatRequest(BaseModel):
    kind: str           # 'dm' | 'group'
    agents: list[str]   # роли из PERSONAS
    title: str | None = None


class SendMessageRequest(BaseModel):
    content: str
    reply_to_id: int | None = None


# ─── REST Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/devteam/agents", dependencies=[Depends(check_token)])
def list_agents() -> list[dict]:
    return [
        {
            "role": p.role,
            "name": p.name,
            "emoji": p.emoji,
            "title": p.title,
            "expertise": p.expertise,
            "character": p.character,
        }
        for p in PERSONAS.values()
    ]


@app.get("/api/devteam/chats", dependencies=[Depends(check_token)])
def list_chats() -> list[dict]:
    return storage.list_chats()


@app.post("/api/devteam/chats", dependencies=[Depends(check_token)])
def create_chat(body: CreateChatRequest) -> dict:
    unknown = [r for r in body.agents if r not in PERSONAS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Неизвестные роли: {unknown}")
    if body.kind not in ("dm", "group"):
        raise HTTPException(status_code=422, detail="kind должен быть 'dm' или 'group'")
    return storage.create_chat(kind=body.kind, agents=body.agents, title=body.title)


@app.get("/api/devteam/chats/{chat_id}", dependencies=[Depends(check_token)])
def get_chat(chat_id: int) -> dict:
    chat = storage.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    return chat


class UpdateChatRequest(BaseModel):
    agents: list[str] | None = None
    title: str | None = None


@app.patch("/api/devteam/chats/{chat_id}", dependencies=[Depends(check_token)])
def patch_chat(chat_id: int, body: UpdateChatRequest) -> dict:
    chat = storage.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    if chat.get("kind") == "dm":
        raise HTTPException(status_code=400, detail="DM-чат нельзя редактировать")
    updates: dict = {}
    if body.agents is not None:
        unknown = [r for r in body.agents if r not in PERSONAS]
        if unknown:
            raise HTTPException(status_code=422, detail=f"Неизвестные роли: {unknown}")
        if len(body.agents) == 0:
            raise HTTPException(status_code=422, detail="Нужен хотя бы один участник")
        updates["agents"] = ",".join(body.agents)
    if body.title is not None:
        updates["title"] = body.title
    if updates:
        storage.update_chat(chat_id, **updates)
    return storage.get_chat(chat_id)


@app.delete("/api/devteam/chats/{chat_id}", dependencies=[Depends(check_token)])
def delete_chat(chat_id: int) -> dict:
    if not storage.get_chat(chat_id):
        raise HTTPException(status_code=404, detail="Чат не найден")
    storage.delete_chat(chat_id)
    return {"ok": True}


@app.get("/api/devteam/chats/{chat_id}/messages", dependencies=[Depends(check_token)])
def get_messages(chat_id: int, offset: int = 0, limit: int = 50) -> list[dict]:
    if not storage.get_chat(chat_id):
        raise HTTPException(status_code=404, detail="Чат не найден")
    return storage.list_messages(chat_id, offset=offset, limit=limit)


@app.post("/api/devteam/chats/{chat_id}/messages", dependencies=[Depends(check_token)])
async def send_message(chat_id: int, body: SendMessageRequest) -> dict:
    chat = storage.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    # Сохраняем сообщение пользователя
    user_msg = storage.create_message(
        chat_id=chat_id,
        author="user",
        content=body.content,
        reply_to_id=body.reply_to_id,
    )
    # Отсылаем пользовательское сообщение подписчикам WS
    await manager.broadcast(chat_id, {"type": "message_created", "message": user_msg})

    # Получаем цитируемое сообщение для контекста агента
    reply_to_msg = storage.get_message(body.reply_to_id) if body.reply_to_id else None

    # Запускаем обработку в фоне (WS-подписчик получит прогресс)
    asyncio.create_task(_handle_message(chat, user_msg["id"], body.content, reply_to_msg))

    return user_msg


async def _handle_message(
    chat: dict, user_msg_id: int, content: str, reply_to_msg: dict | None = None
) -> None:
    chat_id = chat["id"]
    agents = chat["agents"]

    async def broadcast(cid: int, data: dict) -> None:
        await manager.broadcast(cid, data)

    try:
        if chat["kind"] == "dm":
            if len(agents) == 1 and agents[0] == "orchestrator":
                await run_dm_orchestrator(chat_id, content, broadcast, _orchestrator)
            else:
                await run_dm_specialist(chat_id, user_msg_id, content, broadcast, reply_to_msg)
        else:
            await run_group_message(chat_id, content, broadcast, _orchestrator, reply_to_msg)
    except Exception as exc:
        log.exception("Ошибка обработки сообщения в чате %d", chat_id)
        await manager.broadcast(chat_id, {"type": "error", "message": str(exc)})


@app.get("/api/devteam/tasks", dependencies=[Depends(check_token)])
def list_tasks_endpoint(chat_id: int | None = None, status: str | None = None) -> list[dict]:
    return storage.list_tasks(chat_id=chat_id, status=status)


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/api/devteam/chats/{chat_id}/ws")
async def websocket_endpoint(chat_id: int, websocket: WebSocket, token: str = "") -> None:
    if token != config.api_token:
        await websocket.close(code=1008)
        return

    if not storage.get_chat(chat_id):
        await websocket.close(code=1003)
        return

    await manager.connect(chat_id, websocket)
    log.info("WS подключён: chat_id=%d", chat_id)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data: dict[str, Any] = json.loads(raw)
            except Exception:
                continue
            if data.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(chat_id, websocket)
        log.info("WS отключён: chat_id=%d", chat_id)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
