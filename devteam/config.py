from __future__ import annotations

from pydantic_settings import BaseSettings


class DevTeamConfig(BaseSettings):
    # Макс — главный бот
    telegram_bot_token: str = ""

    # Боты специалистов
    bot_token_backend: str = ""
    bot_token_frontend: str = ""
    bot_token_devops: str = ""
    bot_token_ai_engineer: str = ""
    bot_token_analyst: str = ""

    # Группа куда все боты пишут
    group_chat_id: int = 0

    # Разрешённые пользователи (через запятую)
    allowed_chat_ids: str = ""

    # Claude
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    project_root: str = "/opt/myapp"

    bash_deny_patterns: list[str] = [
        "rm -rf /",
        "rm -rf /*",
        "dd if=",
        "> /dev/sd",
        "mkfs",
        ":(){ :|:& };:",
    ]

    model_config = {"env_prefix": "DEVTEAM_", "env_file": "/opt/myapp/devteam/.env"}

    def get_allowed_chat_ids(self) -> list[int]:
        if not self.allowed_chat_ids:
            return []
        return [int(x.strip()) for x in self.allowed_chat_ids.split(",") if x.strip()]

    def specialist_token(self, role: str) -> str:
        """Токен бота специалиста, fallback на токен Макса."""
        return {
            "backend": self.bot_token_backend,
            "frontend": self.bot_token_frontend,
            "devops": self.bot_token_devops,
            "ai_engineer": self.bot_token_ai_engineer,
            "analyst": self.bot_token_analyst,
        }.get(role) or self.telegram_bot_token


config = DevTeamConfig()
