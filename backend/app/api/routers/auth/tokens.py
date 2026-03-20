from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, status
from jose import jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.api.routers.auth.utils import (
    _build_token_payload,
    _create_error_response,
    _create_refresh_token,
    _issue_token,
    build_clear_refresh_cookie_headers,
    set_refresh_cookie,
)
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import hash_refresh_token
from app.db.models.api_key import ApiKey
from app.db.models.refresh_token import RefreshToken
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import TokenResponse
from app.services.api_keys import hash_api_key
from app.services.users import resolve_scopes

logger = structlog.get_logger()

router = APIRouter()


class TokenRequest(BaseModel):
    api_key: str | None = Field(default=None, min_length=1)


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    payload: TokenRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    x_api_key: str | None = Header(default=None, alias="x-api-key"),
) -> TokenResponse:
    settings = get_settings()
    api_key = payload.api_key or x_api_key
    if not api_key:
        raise _create_error_response(
            "invalid_credentials",
            "Missing API key",
            status.HTTP_401_UNAUTHORIZED,
        )

    key_hash = hash_api_key(api_key, settings.api_key_pepper)
    stmt = select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked_at.is_(None))
    api_key_row = (await db.execute(stmt)).scalar_one_or_none()
    if api_key_row:
        api_key_row.last_used_at = datetime.utcnow()
        await db.commit()
        user = await db.get(User, api_key_row.user_id)
        role = user.role if user else "manager"
        token_payload = {
            "sub": str(api_key_row.user_id),
            "tenant_id": str(api_key_row.tenant_id),
            "role": role,
            "scopes": api_key_row.scopes,
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
        }
        token = jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        refresh_token = await _create_refresh_token(db, settings, str(api_key_row.user_id))
        set_refresh_cookie(response, settings, refresh_token)
        return TokenResponse(token=token, refresh_token=None)

    key_info = settings.auth_api_keys.get(api_key)
    if not key_info:
        raise _create_error_response(
            "invalid_credentials",
            "Invalid API key",
            status.HTTP_401_UNAUTHORIZED,
        )

    token_payload = _build_token_payload(settings, key_info)
    token = jwt.encode(token_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    # Для статических API ключей из конфига refresh token не создаем
    return TokenResponse(token=token, refresh_token=None)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(get_settings().rate_limit_auth_refresh)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Обновляет access token используя refresh token."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    refresh_token_value = request.cookies.get(settings.auth_refresh_cookie_name)

    if not refresh_token_value:
        clear_cookie_headers = build_clear_refresh_cookie_headers(settings)
        raise _create_error_response(
            "invalid_refresh_token",
            "Refresh token cookie is missing",
            status.HTTP_401_UNAUTHORIZED,
            headers=clear_cookie_headers,
        )

    # Логируем начало запроса
    logger.info(
        event="refresh_token_request",
        ip=client_ip,
        user_agent=user_agent,
        token_length=len(refresh_token_value),
    )

    # Хешируем переданный refresh token
    token_hash = hash_refresh_token(refresh_token_value, settings.jwt_secret)

    # Ищем refresh token в БД с блокировкой для предотвращения race condition
    try:
        # Используем FOR UPDATE NOWAIT для предотвращения параллельной обработки одного токена
        stmt = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
        ).with_for_update(nowait=True)
        db_refresh_token = (await db.execute(stmt)).scalar_one_or_none()

        # Логируем для диагностики
        logger.info(
            event="refresh_token_lookup",
            token_hash_prefix=token_hash[:16] + "...",
            found=db_refresh_token is not None,
            ip=client_ip,
        )

        # Дополнительная диагностика: проверяем все активные токены пользователя
        if not db_refresh_token:
            # Проверяем, есть ли вообще активные токены для отладки
            all_tokens_stmt = select(RefreshToken).where(
                RefreshToken.revoked_at.is_(None),
            ).limit(5)
            all_tokens = (await db.execute(all_tokens_stmt)).scalars().all()
            logger.warning(
                event="refresh_token_not_found_debug",
                token_hash_prefix=token_hash[:16] + "...",
                total_active_tokens=len(all_tokens),
                sample_hashes=[t.token_hash[:16] + "..." for t in all_tokens[:3]],
                ip=client_ip,
            )
    except Exception as exc:
        # Если токен уже заблокирован другим запросом (обрабатывается параллельно)
        error_str = str(exc).lower()
        error_type = type(exc).__name__.lower()
        if "could not obtain lock" in error_str or "lock_not_available" in error_type or "55p03" in error_str:
            logger.warning(
                event="refresh_token_concurrent_request",
                ip=client_ip,
                user_agent=user_agent,
                reason="token_already_processing",
            )
            raise _create_error_response(
                "refresh_token_in_use",
                "Refresh token is already being processed. Please wait and try again.",
                status.HTTP_409_CONFLICT,
            ) from exc

        # Другие ошибки БД
        logger.exception(
            "refresh_token_db_error",
            error=str(exc),
            error_type=type(exc).__name__,
            ip=client_ip,
        )
        raise _create_error_response(
            "internal_error",
            "Database error. Please ensure migrations are applied.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    if not db_refresh_token:
        clear_cookie_headers = build_clear_refresh_cookie_headers(settings)
        logger.warning(
            event="refresh_token_invalid",
            ip=client_ip,
            user_agent=user_agent,
            reason="token_not_found",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "invalid_refresh_token",
            "Invalid or revoked refresh token",
            status.HTTP_401_UNAUTHORIZED,
            headers=clear_cookie_headers,
        )

    # Проверяем срок действия
    if db_refresh_token.expires_at < datetime.now(timezone.utc):
        clear_cookie_headers = build_clear_refresh_cookie_headers(settings)
        logger.warning(
            event="refresh_token_expired",
            user_id=str(db_refresh_token.user_id),
            ip=client_ip,
            user_agent=user_agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "refresh_token_expired",
            "Refresh token has expired",
            status.HTTP_401_UNAUTHORIZED,
            headers=clear_cookie_headers,
        )

    # Получаем пользователя
    user = await db.get(User, db_refresh_token.user_id)
    if not user or not user.is_active:
        clear_cookie_headers = build_clear_refresh_cookie_headers(settings)
        logger.warning(
            event="refresh_token_user_inactive",
            user_id=str(db_refresh_token.user_id),
            ip=client_ip,
            user_agent=user_agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "account_inactive",
            "User account is inactive",
            status.HTTP_403_FORBIDDEN,
            headers=clear_cookie_headers,
        )

    # Проверяем tenant
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant or not tenant.is_active:
        clear_cookie_headers = build_clear_refresh_cookie_headers(settings)
        logger.warning(
            event="refresh_token_tenant_inactive",
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            ip=client_ip,
            user_agent=user_agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "account_inactive",
            "Tenant is inactive",
            status.HTTP_403_FORBIDDEN,
            headers=clear_cookie_headers,
        )

    # Генерируем новые токены ПЕРЕД отзывом старого (чтобы не потерять доступ при ошибке)
    try:
        scopes = resolve_scopes(user.role, user.scopes)
        token = _issue_token(settings, str(user.id), str(user.tenant_id), scopes, user.role)
        # Создаем новый refresh token БЕЗ commit (commit будет позже)
        refresh_token = await _create_refresh_token(db, settings, str(user.id), commit=False)

        # Отзываем старый refresh token только после успешного создания нового
        db_refresh_token.revoked_at = datetime.now(timezone.utc)

        # Коммитим все изменения одной транзакцией
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception(
            "refresh_token_generation_error",
            error=str(exc),
            error_type=type(exc).__name__,
            user_id=str(user.id),
        )
        raise _create_error_response(
            "internal_error",
            "Failed to generate tokens",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    logger.info(
        event="refresh_token_success",
        user_id=str(user.id),
        ip=client_ip,
        user_agent=user_agent,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    set_refresh_cookie(response, settings, refresh_token)
    return TokenResponse(token=token, refresh_token=None)


@router.get("/test-token")
async def get_test_token():
    """Генерирует временный токен для тестирования в Swagger"""
    settings = get_settings()
    if settings.environment != "dev" and not settings.allow_test_tokens:
        raise _create_error_response(
            "not_found",
            "Not found",
            status.HTTP_404_NOT_FOUND,
        )
    payload = {
        "sub": str(uuid4()),
        "tenant_id": str(uuid4()),
        "scopes": ["tools:write"],
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {"token": token, "note": "Используйте этот токен в кнопке Authorize (Bearer <token>)"}
