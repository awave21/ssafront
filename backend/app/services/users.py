from __future__ import annotations

# Права доступа для каждой роли
# Эти scopes используются фронтендом для управления UI-элементами
ROLE_SCOPES: dict[str, list[str]] = {
    "owner": [
        # Агенты
        "agents:read",
        "agents:write",
        # Участники организации
        "members:manage",
        # Диалоги
        "dialogs:read",
        "dialogs:write",
        "dialogs:delete",
        # Запуски
        "runs:read",
        "runs:write",
        # Аналитика
        "analytics:view",
        # Тарифы моделей
        "model_pricing:read",
        "model_pricing:write",
        # Организация
        "organization:manage",
        # Инструменты
        "tools:read",
        "tools:write",
        # Legacy scopes (для обратной совместимости)
        "users:read",
        "users:manage",
        "users:delete_owner",
        "invitations:read",
        "invitations:write",
        "settings:read",
        "settings:write",
    ],
    "admin": [
        # Агенты
        "agents:read",
        "agents:write",
        # Участники организации
        "members:manage",
        # Диалоги
        "dialogs:read",
        "dialogs:write",
        "dialogs:delete",
        # Запуски
        "runs:read",
        "runs:write",
        # Аналитика
        "analytics:view",
        # Тарифы моделей
        "model_pricing:read",
        "model_pricing:write",
        # Организация
        "organization:manage",
        # Инструменты
        "tools:read",
        "tools:write",
        # Legacy scopes (для обратной совместимости)
        "users:read",
        "users:manage",
        "invitations:read",
        "invitations:write",
        "settings:read",
        "settings:write",
    ],
    "manager": [
        # Агенты (только чтение)
        "agents:read",
        # Диалоги
        "dialogs:read",
        "dialogs:write",
        # Запуски
        "runs:read",
        "runs:write",
        # Аналитика
        "analytics:view",
        # Тарифы моделей
        "model_pricing:read",
        # Инструменты (только чтение)
        "tools:read",
    ],
}

DEFAULT_ROLE_SCOPES: dict[str, list[str]] = ROLE_SCOPES


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_scopes_for_role(role: str) -> list[str]:
    """Возвращает список scopes для указанной роли.
    
    Всегда возвращает актуальные scopes на основе роли,
    игнорируя сохранённые в БД значения.
    """
    return ROLE_SCOPES.get(role, ROLE_SCOPES["manager"])


def resolve_scopes(role: str, scopes: list[str] | None) -> list[str]:
    """Определяет scopes для пользователя.
    
    Теперь всегда возвращает scopes на основе роли,
    чтобы гарантировать актуальность прав доступа.
    """
    # Всегда используем scopes на основе роли для консистентности
    return get_scopes_for_role(role)
