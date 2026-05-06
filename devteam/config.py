from __future__ import annotations

from pydantic_settings import BaseSettings


class DevTeamConfig(BaseSettings):
    # PostgreSQL
    database_url: str = "postgresql://devteam:devteam@localhost:5433/devteam"

    # API-токен для авторизации запросов фронта к devteam-API
    api_token: str = "devteam-secret"

    # FastAPI сервер
    host: str = "0.0.0.0"
    port: int = 8090

    # Рабочая директория агентов (песочница)
    default_cwd: str = "/Users/maksimmoskovec/Documents/ИИ агенты/Агентская система/ssafront"

    # Модель Claude
    model: str = "claude-sonnet-4-6"

    # Максимум tool-use итераций за один запуск агента
    max_turns_per_run: int = 25

    # Паттерны bash-команд, которые блокируются (can_use_tool callback)
    bash_deny_patterns: list[str] = [
        "rm -rf /",
        "rm -rf /*",
        "dd if=",
        "> /dev/sd",
        "mkfs",
        ":(){ :|:& };:",
    ]

    # Опциональный путь к claude CLI (если не в PATH)
    cli_path: str | None = None

    model_config = {"env_prefix": "DEVTEAM_", "env_file": ["/opt/myapp/devteam/.env", "./devteam/.env"]}


config = DevTeamConfig()
