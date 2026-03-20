"""
Единый модуль маппинга сообщений pydantic-ai → формат фронтенда.

Используется в:
- ws.py          (real-time события WebSocket)
- messages.py    (SSE-события и загрузка истории)
- webhooks.py    (определение типа сообщения при фильтрации)
"""
from __future__ import annotations

from typing import Any

# ─── part_kind множества ────────────────────────────────────────────
_USER_PART_KINDS = frozenset({"user-prompt", "user_prompt", "user"})
_SYSTEM_PART_KINDS = frozenset({"system-prompt", "system_prompt", "system"})
_MANAGER_PART_KINDS = frozenset({"manager-message", "manager_message", "manager"})
_TOOL_CALL_PART_KINDS = frozenset({"tool-call", "tool_call"})
_TOOL_RETURN_PART_KINDS = frozenset({"tool-return", "tool_return"})

# ─── pydantic-ai роли → фронтенд роли ──────────────────────────────
_ROLE_MAP: dict[str, str] = {
    "model": "agent",
    "assistant": "agent",
    "user": "user",
    "system": "system",
    "manager": "manager",
}


def infer_role(msg_data: dict[str, Any]) -> str:
    """
    Определить роль сообщения.

    1. Если в ``msg_data`` есть явное поле ``role`` — используем его.
    2. Иначе смотрим ``part_kind`` в ``parts``.
    3. Fallback — ``"agent"``.
    """
    role = msg_data.get("role")
    if role and role != "unknown":
        return _ROLE_MAP.get(role, "agent")

    parts = msg_data.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if isinstance(part, dict):
                pk = part.get("part_kind") or part.get("partKind")
                if pk in _USER_PART_KINDS:
                    return "user"
                if pk in _SYSTEM_PART_KINDS:
                    return "system"
                if pk in _MANAGER_PART_KINDS:
                    return "manager"
    return "agent"


def is_user_prompt(message: dict[str, Any]) -> bool:
    """Является ли сообщение пользовательским промптом."""
    return infer_role(message) == "user"


def extract_user_info(msg_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Безопасно извлечь ``user_info`` из сообщения.

    Ищет в корне и во вложенном ``metadata``.
    """
    info = msg_data.get("user_info")
    if info:
        return info
    metadata = msg_data.get("metadata")
    if isinstance(metadata, dict):
        return metadata.get("user_info") or None
    return None


def extract_text_contents(msg_data: dict[str, Any]) -> list[str]:
    """
    Извлечь все текстовые фрагменты из pydantic-ai сообщения.

    Стратегия:
    1. parts → content / text
    2. Вложенные parts (один уровень)
    3. Корневые content / text
    4. Fallback по известным ключам
    """
    contents = [
        str(part.get("content", ""))
        for part in extract_structured_parts(msg_data)
        if part.get("kind") == "text" and part.get("content")
    ]
    if contents:
        return contents

    # 3. Корневые поля
    root_text = msg_data.get("content") or msg_data.get("text")
    if root_text and str(root_text) not in contents:
        contents.append(str(root_text))

    # 4. Fallback — перебираем типичные ключи
    if not contents:
        for key in ("parts", "content", "text", "message"):
            val = msg_data.get(key)
            if isinstance(val, str) and val:
                contents.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        contents.append(item)
                    elif isinstance(item, dict):
                        t = item.get("content") or item.get("text")
                        if t:
                            contents.append(str(t))

    if not contents:
        for key in ("content", "text", "body", "input", "output"):
            val = msg_data.get(key)
            if isinstance(val, str) and val:
                contents.append(val)

    return contents


def _iter_parts(msg_data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_parts = msg_data.get("parts")
    if not isinstance(raw_parts, list):
        return []

    collected: list[dict[str, Any]] = []
    for part in raw_parts:
        if not isinstance(part, dict):
            continue
        collected.append(part)
        nested_parts = part.get("parts")
        if isinstance(nested_parts, list):
            for nested in nested_parts:
                if isinstance(nested, dict):
                    collected.append(nested)
    return collected


def _normalize_dict_like(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
    return None


def extract_structured_parts(msg_data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Извлечь структурные части сообщения:
    - text
    - tool-call
    - tool-return
    """
    structured_parts: list[dict[str, Any]] = []

    for part in _iter_parts(msg_data):
        part_kind = part.get("part_kind") or part.get("partKind")
        text = part.get("content") or part.get("text")

        if part_kind in _TOOL_CALL_PART_KINDS:
            args = _normalize_dict_like(part.get("args") or part.get("arguments")) or {}
            structured_parts.append(
                {
                    "kind": "tool-call",
                    "part_kind": part_kind,
                    "tool_name": part.get("tool_name") or part.get("name"),
                    "tool_call_id": part.get("tool_call_id") or part.get("id"),
                    "args": args,
                }
            )
            continue

        if part_kind in _TOOL_RETURN_PART_KINDS:
            result = part.get("result")
            if result is None:
                result = part.get("content")
            payload = _normalize_dict_like(result) or {}
            args = _normalize_dict_like(part.get("args") or part.get("arguments"))
            if args is None:
                args = _normalize_dict_like(payload.get("args"))
            structured_parts.append(
                {
                    "kind": "tool-return",
                    "part_kind": part_kind,
                    "tool_name": part.get("tool_name") or part.get("name") or payload.get("tool_name"),
                    "tool_call_id": part.get("tool_call_id") or part.get("id"),
                    "args": args,
                    "result": result,
                }
            )
            continue

        if text:
            structured_parts.append(
                {
                    "kind": "text",
                    "part_kind": part_kind,
                    "content": str(text),
                }
            )

    root_text = msg_data.get("content") or msg_data.get("text")
    if root_text:
        root_text_str = str(root_text)
        if not any(
            part.get("kind") == "text" and part.get("content") == root_text_str
            for part in structured_parts
        ):
            structured_parts.append(
                {
                    "kind": "text",
                    "part_kind": None,
                    "content": root_text_str,
                }
            )

    return structured_parts


def build_user_prompt(text: str) -> dict[str, Any]:
    """Собрать сообщение пользователя в формате pydantic-ai."""
    return {
        "parts": [
            {
                "part_kind": "user-prompt",
                "content": text,
            }
        ]
    }


def build_manager_message(text: str) -> dict[str, Any]:
    """Собрать сообщение менеджера."""
    return {
        "role": "manager",
        "parts": [
            {
                "part_kind": "manager-message",
                "content": text,
            }
        ],
    }


def filter_user_prompts(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Отфильтровать пользовательские промпты из списка сообщений."""
    return [m for m in messages if not is_user_prompt(m)]
