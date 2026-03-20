from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, Response, status
from jose import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.core.config import Settings
from app.core.security import generate_refresh_token, hash_refresh_token, parse_token_expires_in
from app.db.models.refresh_token import RefreshToken

logger = structlog.get_logger()


def _refresh_cookie_max_age_seconds(settings: Settings) -> int:
    ttl = parse_token_expires_in(settings.jwt_refresh_token_expires_in)
    return max(int(ttl.total_seconds()), 1)


def set_refresh_cookie(response: Response, settings: Settings, refresh_token: str) -> None:
    max_age_seconds = _refresh_cookie_max_age_seconds(settings)
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        max_age=max_age_seconds,
        expires=max_age_seconds,
        path=settings.auth_refresh_cookie_path,
        domain=settings.auth_refresh_cookie_domain,
        secure=settings.auth_refresh_cookie_secure,
        httponly=True,
        samesite=settings.auth_refresh_cookie_samesite,
    )


def clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value="",
        max_age=0,
        expires=0,
        path=settings.auth_refresh_cookie_path,
        domain=settings.auth_refresh_cookie_domain,
        secure=settings.auth_refresh_cookie_secure,
        httponly=True,
        samesite=settings.auth_refresh_cookie_samesite,
    )


def build_clear_refresh_cookie_headers(settings: Settings) -> dict[str, str]:
    probe_response = Response()
    clear_refresh_cookie(probe_response, settings)
    set_cookie_header = probe_response.headers.get("set-cookie")
    if not set_cookie_header:
        return {}
    return {"Set-Cookie": set_cookie_header}


def _create_error_response(
    error_code: str,
    message: str,
    status_code: int,
    details: dict[str, list[str]] | None = None,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """Создает HTTPException со стандартизированным форматом ошибок."""
    content = {
        "error": error_code,
        "message": message,
    }
    if details:
        content["details"] = details
    return HTTPException(status_code=status_code, detail=content, headers=headers)


def _build_token_payload(settings: Settings, key_info: dict[str, str | list[str]]) -> dict[str, str | list[str]]:
    tenant_id = key_info.get("tenant_id")
    user_id = key_info.get("user_id")
    scopes = key_info.get("scopes", [])
    role = key_info.get("role", "admin")
    if not tenant_id or not user_id:
        raise _create_error_response(
            "internal_error",
            "AUTH_API_KEYS entry must include tenant_id and user_id",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": str(role),
        "scopes": scopes if isinstance(scopes, list) else [],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }


def _issue_token(
    settings: Settings, user_id: str, tenant_id: str, scopes: list[str], role: str = "manager"
) -> str:
    try:
        now = datetime.utcnow()
        expires_in = parse_token_expires_in(settings.jwt_access_token_expires_in)

        token_payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "scopes": scopes,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "exp": int((now + expires_in).timestamp()),
            "iat": int(now.timestamp()),
            "jti": str(uuid4()),
        }
        return jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    except Exception as exc:
        try:
            logger.error(
                event="token_generation_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                user_id=user_id,
                tenant_id=tenant_id,
            )
        except Exception:
            pass  # Если логирование не работает, продолжаем
        raise _create_error_response(
            "internal_error",
            "Failed to generate token",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


async def _create_refresh_token(
    db: AsyncSession,
    settings: Settings,
    user_id: str | UUID,
    commit: bool = True,
) -> str:
    """Создает и сохраняет refresh token в БД.

    Args:
        db: сессия базы данных
        settings: настройки приложения
        user_id: ID пользователя (str или UUID)
        commit: выполнять ли commit (по умолчанию True)

    Returns:
        Открытый refresh token (не хеш)
    """
    refresh_token = generate_refresh_token()
    token_hash = hash_refresh_token(refresh_token, settings.jwt_secret)
    expires_in = parse_token_expires_in(settings.jwt_refresh_token_expires_in)
    expires_at = datetime.now(timezone.utc) + expires_in

    # Конвертируем user_id в UUID если это строка
    user_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

    db_refresh_token = RefreshToken(
        user_id=user_uuid,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(db_refresh_token)

    if commit:
        try:
            await db.commit()
            logger.debug(
                event="refresh_token_created",
                user_id=str(user_uuid),
                expires_at=expires_at.isoformat(),
            )
        except IntegrityError as exc:
            # Обработка коллизии токенов (крайне маловероятно, но возможно)
            await db.rollback()
            logger.warning(
                "refresh_token_hash_collision",
                user_id=str(user_uuid),
                error=str(exc),
            )
            # Повторяем попытку с новым токеном
            return await _create_refresh_token(db, settings, user_id, commit=commit)
        except Exception as exc:
            await db.rollback()
            logger.exception(
                "refresh_token_creation_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                user_id=str(user_uuid),
            )
            raise

    return refresh_token
