from __future__ import annotations

import sqlite3
from datetime import datetime
from enum import Enum
from pathlib import Path

DB_PATH = Path(__file__).parent / "tasks.db"


class Priority(str, Enum):
    urgent = "🔴 Срочно"
    high = "🟡 Важно"
    normal = "🟢 Обычно"


class Status(str, Enum):
    pending = "pending"
    clarifying = "clarifying"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"


def _conn() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     INTEGER NOT NULL,
                message_id  INTEGER,
                description TEXT    NOT NULL,
                priority    TEXT    NOT NULL DEFAULT '🟢 Обычно',
                agent_role  TEXT,
                status      TEXT    NOT NULL DEFAULT 'pending',
                result      TEXT,
                created_at  TEXT    NOT NULL,
                updated_at  TEXT    NOT NULL
            )
        """)
        con.commit()


def create_task(
    chat_id: int,
    description: str,
    priority: Priority = Priority.normal,
    agent_role: str | None = None,
    message_id: int | None = None,
) -> int:
    now = datetime.utcnow().isoformat()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO tasks (chat_id, message_id, description, priority, agent_role, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, message_id, description, priority.value, agent_role, Status.pending.value, now, now),
        )
        con.commit()
        return cur.lastrowid  # type: ignore[return-value]


def update_task(task_id: int, **kwargs: object) -> None:
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    cols = ", ".join(f"{k} = ?" for k in kwargs)
    with _conn() as con:
        con.execute(f"UPDATE tasks SET {cols} WHERE id = ?", [*kwargs.values(), task_id])
        con.commit()


def list_tasks(chat_id: int, status: str | None = None) -> list[dict]:
    with _conn() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM tasks WHERE chat_id = ? AND status = ? ORDER BY id DESC LIMIT 20",
                (chat_id, status),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM tasks WHERE chat_id = ? ORDER BY id DESC LIMIT 20",
                (chat_id,),
            ).fetchall()
        return [dict(r) for r in rows]


init_db()
