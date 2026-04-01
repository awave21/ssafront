from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from jose import JWTError, jwt

from app.core.config import get_settings
from app.schemas.auth import AuthContext, TokenPayload
from app.services.users import get_scopes_for_role


class AuthError(Exception):
    pass


def parse_token_expires_in(value: str) -> timedelta:
    """Парсит строку формата '15m', '1h', '900s' в timedelta."""
    if not value:
        return timedelta(minutes=15)  # Значение по умолчанию
    
    value = value.strip().lower()
    try:
        if value.endswith("s"):
            seconds = int(value[:-1])
            return timedelta(seconds=seconds)
        elif value.endswith("m"):
            minutes = int(value[:-1])
            return timedelta(minutes=minutes)
        elif value.endswith("h"):
            hours = int(value[:-1])
            return timedelta(hours=hours)
        elif value.endswith("d"):
            days = int(value[:-1])
            return timedelta(days=days)
        else:
            # По умолчанию считаем, что это минуты
            return timedelta(minutes=int(value))
    except (ValueError, AttributeError):
        # Если не удалось распарсить, возвращаем значение по умолчанию
        return timedelta(minutes=15)


def decode_token(token: str) -> AuthContext:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except JWTError as exc:
        raise AuthError("Invalid token") from exc

    token_payload = TokenPayload.model_validate(payload)
    role = getattr(token_payload, "role", "manager")
    # Всегда берём scopes из актуальной матрицы роли: в JWT мог остаться устаревший
    # список (до смены роли или обновления прав), иначе владелец мог терять billing:write и др.
    scopes = get_scopes_for_role(role)

    return AuthContext(
        user_id=token_payload.user_id,
        tenant_id=token_payload.tenant_id,
        role=role,
        scopes=scopes,
    )


def generate_refresh_token() -> str:
    """Генерирует случайный refresh token."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str, pepper: str) -> str:
    """Хеширует refresh token для безопасного хранения."""
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()
