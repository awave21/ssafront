"""Сервисы исходящей отправки сообщений."""

from app.services.outbound.manager_dispatcher import (
    ManagerDispatchError,
    ManagerDispatchResult,
    dispatch_manager_message,
)

__all__ = [
    "ManagerDispatchError",
    "ManagerDispatchResult",
    "dispatch_manager_message",
]
