"""PostgreSQL-хранилище для devteam: чаты, сообщения, задачи."""
from __future__ import annotations

import json
from datetime import datetime

import psycopg2
import psycopg2.extras

from devteam.config import config


def _conn():
    con = psycopg2.connect(config.database_url)
    con.autocommit = False
    return con


def init_db() -> None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                    id         SERIAL PRIMARY KEY,
                    kind       TEXT    NOT NULL,
                    title      TEXT,
                    agents     TEXT    NOT NULL,
                    session_id TEXT,
                    created_at TEXT    NOT NULL,
                    updated_at TEXT    NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id          SERIAL PRIMARY KEY,
                    chat_id     INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    author      TEXT    NOT NULL,
                    content     TEXT    NOT NULL,
                    tool_calls  TEXT,
                    task_id     INTEGER,
                    reply_to_id INTEGER REFERENCES messages(id) ON DELETE SET NULL,
                    created_at  TEXT    NOT NULL
                )
            """)
            cur.execute("""
                ALTER TABLE messages ADD COLUMN IF NOT EXISTS
                    reply_to_id INTEGER REFERENCES messages(id) ON DELETE SET NULL
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          SERIAL PRIMARY KEY,
                    chat_id     INTEGER NOT NULL,
                    description TEXT    NOT NULL,
                    priority    TEXT    NOT NULL DEFAULT '🟢 Обычно',
                    agent_roles TEXT,
                    status      TEXT    NOT NULL DEFAULT 'pending',
                    created_at  TEXT    NOT NULL,
                    updated_at  TEXT    NOT NULL
                )
            """)
        con.commit()


# ─── Chats ────────────────────────────────────────────────────────────────────

def create_chat(kind: str, agents: list[str], title: str | None = None) -> dict:
    now = _now()
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO chats (kind, title, agents, created_at, updated_at) VALUES (%s, %s, %s, %s, %s) RETURNING *",
                (kind, title, ",".join(agents), now, now),
            )
            row = cur.fetchone()
        con.commit()
    return _chat_dict(dict(row))


def get_chat(chat_id: int) -> dict:
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM chats WHERE id = %s", (chat_id,))
            row = cur.fetchone()
    return _chat_dict(dict(row)) if row else {}


def list_chats() -> list[dict]:
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM chats ORDER BY updated_at DESC")
            rows = cur.fetchall()
    return [_chat_dict(dict(r)) for r in rows]


def update_chat(chat_id: int, **kwargs) -> None:
    kwargs["updated_at"] = _now()
    cols = ", ".join(f"{k} = %s" for k in kwargs)
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE chats SET {cols} WHERE id = %s", [*kwargs.values(), chat_id])
        con.commit()


def delete_chat(chat_id: int) -> None:
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute("DELETE FROM chats WHERE id = %s", (chat_id,))
        con.commit()


def _chat_dict(d: dict) -> dict:
    d["agents"] = d["agents"].split(",") if d.get("agents") else []
    return d


# ─── Messages ─────────────────────────────────────────────────────────────────

def get_message(message_id: int) -> dict | None:
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, chat_id, author, content FROM messages WHERE id = %s", (message_id,))
            row = cur.fetchone()
    return dict(row) if row else None


def create_message(
    chat_id: int,
    author: str,
    content: str,
    tool_calls: list[dict] | None = None,
    task_id: int | None = None,
    reply_to_id: int | None = None,
) -> dict:
    now = _now()
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                WITH ins AS (
                    INSERT INTO messages (chat_id, author, content, tool_calls, task_id, reply_to_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *
                )
                SELECT ins.*, rm.author AS reply_author, LEFT(rm.content, 120) AS reply_preview
                FROM ins
                LEFT JOIN messages rm ON rm.id = ins.reply_to_id
                """,
                (chat_id, author, content, json.dumps(tool_calls) if tool_calls else None, task_id, reply_to_id, now),
            )
            row = cur.fetchone()
        con.commit()
    return _msg_dict(dict(row))


def list_messages(chat_id: int, offset: int = 0, limit: int = 50) -> list[dict]:
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT m.id, m.chat_id, m.author, m.content, m.tool_calls, m.task_id,
                       m.reply_to_id, m.created_at,
                       rm.author  AS reply_author,
                       LEFT(rm.content, 120) AS reply_preview
                FROM messages m
                LEFT JOIN messages rm ON rm.id = m.reply_to_id
                WHERE m.chat_id = %s ORDER BY m.id ASC LIMIT %s OFFSET %s
                """,
                (chat_id, limit, offset),
            )
            rows = cur.fetchall()
    return [_msg_dict(dict(r)) for r in rows]


def _msg_dict(d: dict) -> dict:
    if d.get("tool_calls"):
        try:
            d["tool_calls"] = json.loads(d["tool_calls"])
        except Exception:
            d["tool_calls"] = []
    else:
        d["tool_calls"] = []

    # Собираем reply_to из JOIN-полей
    reply_author  = d.pop("reply_author", None)
    reply_preview = d.pop("reply_preview", None)
    if d.get("reply_to_id") and reply_author is not None:
        d["reply_to"] = {
            "id":      d["reply_to_id"],
            "author":  reply_author,
            "content": reply_preview or "",
        }
    else:
        d["reply_to"] = None
    return d


# ─── Tasks ────────────────────────────────────────────────────────────────────

def create_task(
    chat_id: int,
    description: str,
    priority: str = "🟢 Обычно",
    agent_roles: list[str] | None = None,
) -> dict:
    now = _now()
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO tasks (chat_id, description, priority, agent_roles, status, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
                (chat_id, description, priority, ",".join(agent_roles) if agent_roles else None, "pending", now, now),
            )
            row = cur.fetchone()
        con.commit()
    return _task_dict(dict(row))


def get_task(task_id: int) -> dict:
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
            row = cur.fetchone()
    return _task_dict(dict(row)) if row else {}


def update_task(task_id: int, **kwargs) -> None:
    kwargs["updated_at"] = _now()
    cols = ", ".join(f"{k} = %s" for k in kwargs)
    with _conn() as con:
        with con.cursor() as cur:
            cur.execute(f"UPDATE tasks SET {cols} WHERE id = %s", [*kwargs.values(), task_id])
        con.commit()


def list_tasks(chat_id: int | None = None, status: str | None = None) -> list[dict]:
    parts = ["SELECT * FROM tasks WHERE 1=1"]
    params: list = []
    if chat_id is not None:
        parts.append("AND chat_id = %s")
        params.append(chat_id)
    if status:
        parts.append("AND status = %s")
        params.append(status)
    parts.append("ORDER BY id DESC LIMIT 50")
    with _conn() as con:
        with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(" ".join(parts), params)
            rows = cur.fetchall()
    return [_task_dict(dict(r)) for r in rows]


def _task_dict(d: dict) -> dict:
    d["agent_roles"] = d["agent_roles"].split(",") if d.get("agent_roles") else []
    return d


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.utcnow().isoformat()


init_db()
