"""Specialist agent — выполняет задачу используя Claude + инструменты."""
from __future__ import annotations

from typing import Callable

import anthropic

from devteam.config import config
from devteam.agents.personas import Persona
from devteam.tools.file_tools import read_file, write_file, list_directory, search_code
from devteam.tools.bash_tools import bash_execute
from devteam.tools.git_tools import git_status, git_diff, git_log, git_commit

TOOLS: list[dict] = [
    {
        "name": "read_file",
        "description": "Читает файл проекта. Путь относительно /opt/myapp или абсолютный.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    },
    {
        "name": "write_file",
        "description": "Записывает содержимое в файл. Создаёт директории если нужно.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "Список файлов в директории проекта.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}},
        },
    },
    {
        "name": "search_code",
        "description": "Поиск по коду (grep). Возвращает строки с совпадением.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "file_glob": {"type": "string"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "bash_execute",
        "description": "Выполняет bash-команду в директории проекта.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer"},
                "workdir": {"type": "string"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "git_status",
        "description": "Текущий git status.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "git_diff",
        "description": "Git diff изменений.",
        "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}},
    },
    {
        "name": "git_log",
        "description": "Последние коммиты.",
        "input_schema": {"type": "object", "properties": {"n": {"type": "integer"}}},
    },
    {
        "name": "git_commit",
        "description": "Создаёт git commit со всеми изменениями.",
        "input_schema": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]},
    },
]


def _run_tool(name: str, inp: dict) -> str:
    match name:
        case "read_file":       return read_file(inp["path"])
        case "write_file":      return write_file(inp["path"], inp["content"])
        case "list_directory":  return list_directory(inp.get("path", ""), inp.get("pattern", "*"))
        case "search_code":     return search_code(inp["pattern"], inp.get("path", ""), inp.get("file_glob", "*.py"))
        case "bash_execute":    return bash_execute(inp["command"], inp.get("timeout", 60), inp.get("workdir") or None)
        case "git_status":      return git_status()
        case "git_diff":        return git_diff(inp.get("path", ""))
        case "git_log":         return git_log(inp.get("n", 10))
        case "git_commit":      return git_commit(inp["message"])
        case _:                 return f"[unknown tool: {name}]"


class SpecialistAgent:
    def __init__(self, persona: Persona) -> None:
        self.persona = persona
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def _system(self) -> str:
        p = self.persona
        return (
            f"Ты {p.name} ({p.title}) в команде разработки ChatMedBot — "
            f"многотенантной AI-платформы для медицинских клиник.\n\n"
            f"Характер: {p.character}\n\n"
            f"Специализация: {p.expertise}\n\n"
            f"Проект: /opt/myapp\n"
            f"Backend: FastAPI + Python 3.12 + SQLAlchemy + PostgreSQL + PydanticAI\n"
            f"Frontend: Nuxt 3 + Vue 3 + TypeScript + Tailwind\n"
            f"Инфра: Docker Compose + Caddy\n\n"
            f"Правила:\n"
            f"- Сначала изучи код, потом меняй\n"
            f"- Если задача затрагивает БД — упомяни нужна ли миграция\n"
            f"- В конце перечисли изменённые файлы\n"
            f"- Отвечай на русском\n"
            f"- Подписывай каждое сообщение: {p.emoji} {p.name}"
        )

    async def run(self, task: str, on_update: Callable[[str], None] | None = None) -> str:
        messages: list[dict] = [{"role": "user", "content": task}]
        result_parts: list[str] = []

        for _ in range(25):
            response = self._client.messages.create(
                model=config.claude_model,
                max_tokens=4096,
                system=self._system(),
                tools=TOOLS,
                messages=messages,
            )

            for block in response.content:
                if block.type == "text" and block.text.strip():
                    result_parts.append(block.text)
                    if on_update:
                        on_update(block.text)

            if response.stop_reason != "tool_use":
                break

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                out = _run_tool(block.name, block.input)
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
                if on_update:
                    on_update(f"🔨 `{block.name}({list(block.input.keys())})` → {out[:150]}")

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        return "\n\n".join(result_parts)
