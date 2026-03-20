from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.api.deps import get_current_user
from app.api.routers.auth.utils import (
    _create_error_response,
    _create_refresh_token,
    _issue_token,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import hash_refresh_token
from app.db.models.refresh_token import RefreshToken
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import AuthContext, AuthTokenResponse, LogoutResponse
from app.schemas.tenant import TenantRead
from app.schemas.invitation import InvitationAccept
from app.schemas.user import UserLogin, UserRead, UserRegister, UserSession
from app.services.passwords import hash_password, verify_password
from app.services.invitations import get_invitation_by_token
from app.services.auth_bruteforce import login_bruteforce_guard
from app.services.users import get_scopes_for_role, normalize_email, resolve_scopes
from app.utils.debug_logging import emit_debug_log

logger = structlog.get_logger()

router = APIRouter()


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_settings().rate_limit_auth_register)
async def register(
    payload: UserRegister,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    settings = get_settings()
    normalized_email = normalize_email(payload.email)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    existing_user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if existing_user is not None:
        raise _create_error_response(
            "email_exists",
            "Пользователь с таким email уже зарегистрирован. Используйте вход вместо регистрации.",
            status.HTTP_409_CONFLICT,
        )

    tenant_name = payload.tenant_name
    if not tenant_name:
        tenant_name = f"Организация {normalized_email}"

    tenant_id = uuid4()
    user = User(
        tenant_id=tenant_id,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="owner",
        scopes=resolve_scopes("owner", None),
        is_active=True,
    )
    tenant = Tenant(id=tenant_id, name=tenant_name, owner_user_id=user.id)
    db.add_all([user, tenant])
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise _create_error_response(
            "email_exists",
            "Пользователь с таким email уже зарегистрирован. Используйте вход вместо регистрации.",
            status.HTTP_409_CONFLICT,
        ) from exc

    await db.refresh(tenant)
    await db.refresh(user)

    scopes = get_scopes_for_role(user.role)
    token = _issue_token(settings, str(user.id), str(tenant.id), scopes, user.role)
    refresh_token = await _create_refresh_token(db, settings, str(user.id))
    set_refresh_cookie(response, settings, refresh_token)

    # Логирование успешной регистрации
    logger.info(
        event="register_success",
        user_id=str(user.id),
        email=normalized_email,
        ip=client_ip,
        user_agent=user_agent,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    # Создаём UserRead с актуальными scopes на основе роли
    user_data = UserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        scopes=scopes,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )

    return AuthTokenResponse(
        token=token,
        refresh_token=None,
        user=user_data,
        tenant=TenantRead.model_validate(tenant),
    )


@router.post("/register-by-invite", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_settings().rate_limit_auth_register)
async def register_by_invite(
    payload: InvitationAccept,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    """Принять приглашение и зарегистрироваться в организации."""
    settings = get_settings()
    invitation = await get_invitation_by_token(db, payload.token, settings.jwt_secret)
    if not invitation:
        raise _create_error_response(
            "invalid_or_expired_token",
            "Ссылка приглашения недействительна или истекла",
            status.HTTP_400_BAD_REQUEST,
        )
    normalized_email = normalize_email(invitation.email)
    existing_user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    if existing_user:
        raise _create_error_response(
            "user_exists",
            "Пользователь с таким email уже зарегистрирован",
            status.HTTP_409_CONFLICT,
        )
    user = User(
        tenant_id=invitation.tenant_id,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=invitation.role,
        scopes=resolve_scopes(invitation.role, None),
        is_active=True,
    )
    db.add(user)
    await db.delete(invitation)
    await db.commit()
    await db.refresh(user)
    tenant = await db.get(Tenant, invitation.tenant_id)
    if not tenant:
        raise _create_error_response("internal_error", "Tenant not found", status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    scopes = get_scopes_for_role(user.role)
    token = _issue_token(settings, str(user.id), str(user.tenant_id), scopes, user.role)
    refresh_token = await _create_refresh_token(db, settings, str(user.id))
    set_refresh_cookie(response, settings, refresh_token)
    
    # Создаём UserRead с актуальными scopes на основе роли
    user_data = UserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        scopes=scopes,
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
    
    return AuthTokenResponse(
        token=token,
        refresh_token=None,
        user=user_data,
        tenant=TenantRead.model_validate(tenant),
    )


@router.post("/login", response_model=AuthTokenResponse)
@limiter.limit(get_settings().rate_limit_auth_login)
async def login(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> AuthTokenResponse:
    settings = get_settings()
    normalized_email = normalize_email(payload.email)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")

    block_state = await login_bruteforce_guard.get_block_state(client_ip, normalized_email)
    if block_state.is_blocked:
        retry_after = max(int(block_state.retry_after_seconds or 0), 1)
        logger.warning(
            event="login_blocked",
            email=normalized_email,
            ip=client_ip,
            user_agent=user_agent,
            reason=block_state.reason or "unknown",
            retry_after=retry_after,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many login attempts. Please try again later.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # region agent log
    emit_debug_log(
        location="backend/app/api/routers/auth/sessions.py:login:start",
        message="login start",
        data={"normalized_email": normalized_email},
        hypothesisId="H1",
    )
    # endregion
    user = (await db.execute(select(User).where(User.email == normalized_email))).scalar_one_or_none()
    # region agent log
    emit_debug_log(
        location="backend/app/api/routers/auth/sessions.py:login:user_lookup",
        message="user lookup result",
        data={
            "user_found": user is not None,
            "user_id": str(user.id) if user else None,
        },
        hypothesisId="H1",
    )
    # endregion

    if user is None or not verify_password(payload.password, user.password_hash):
        await login_bruteforce_guard.register_failed_attempt(client_ip, normalized_email)
        # Логирование неудачной попытки входа
        logger.warning(
            event="login_failed",
            user_id=str(user.id) if user else None,
            email=normalized_email,
            ip=client_ip,
            user_agent=user_agent,
            reason="invalid_credentials",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "invalid_credentials",
            "Invalid email or password",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        # Логирование неудачной попытки входа (неактивный аккаунт)
        logger.warning(
            event="login_failed",
            user_id=str(user.id),
            email=normalized_email,
            ip=client_ip,
            user_agent=user_agent,
            reason="account_inactive",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "account_inactive",
            "Account is inactive",
            status.HTTP_403_FORBIDDEN,
        )

    tenant = await db.get(Tenant, user.tenant_id)
    # region agent log
    emit_debug_log(
        location="backend/app/api/routers/auth/sessions.py:login:tenant_fetch",
        message="tenant fetch result",
        data={
            "tenant_found": tenant is not None,
            "tenant_active": tenant.is_active if tenant else None,
        },
        hypothesisId="H1",
    )
    # endregion
    if tenant is None or not tenant.is_active:
        # Логирование неудачной попытки входа (неактивный tenant)
        logger.warning(
            event="login_failed",
            user_id=str(user.id),
            email=normalized_email,
            ip=client_ip,
            user_agent=user_agent,
            reason="account_inactive",
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
        raise _create_error_response(
            "account_inactive",
            "Tenant is inactive",
            status.HTTP_403_FORBIDDEN,
        )

    await login_bruteforce_guard.clear_failed_attempts(client_ip, normalized_email)

    user.last_login_at = datetime.utcnow()
    # region agent log
    emit_debug_log(
        location="backend/app/api/routers/auth/sessions.py:login:pre_commit",
        message="pre-commit user update",
        data={"user_id": str(user.id)},
        hypothesisId="H3",
    )
    # endregion
    await db.commit()
    # region agent log
    emit_debug_log(
        location="backend/app/api/routers/auth/sessions.py:login:commit",
        message="commit succeeded",
        data={"user_id": str(user.id)},
        hypothesisId="H3",
    )
    # endregion
    await db.refresh(user)

    try:
        scopes = resolve_scopes(user.role, user.scopes)
        token = _issue_token(settings, str(user.id), str(user.tenant_id), scopes, user.role)
        refresh_token = await _create_refresh_token(db, settings, str(user.id))
        set_refresh_cookie(response, settings, refresh_token)
    except Exception as exc:
        logger.exception(
            "token_generation_error_in_login",
            error=str(exc),
            error_type=type(exc).__name__,
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
        )
        raise _create_error_response(
            "internal_error",
            "Failed to generate authentication token",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    # Логирование успешного входа
    try:
        logger.info(
            event="login_success",
            user_id=str(user.id),
            email=normalized_email,
            ip=client_ip,
            user_agent=user_agent,
            timestamp=datetime.utcnow().isoformat() + "Z",
        )
    except Exception:
        pass  # Если логирование не работает, продолжаем

    try:
        # Создаём UserRead с актуальными scopes на основе роли
        user_data = UserRead(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            scopes=scopes,  # Используем scopes из resolve_scopes, а не из БД
            is_active=user.is_active,
            last_login_at=user.last_login_at,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )
        
        return AuthTokenResponse(
            token=token,
            refresh_token=None,
            user=user_data,
            tenant=TenantRead.model_validate(tenant),
        )
    except Exception as exc:
        logger.exception(
            "response_serialization_error",
            error=str(exc),
            error_type=type(exc).__name__,
            user_id=str(user.id),
        )
        raise _create_error_response(
            "internal_error",
            "Failed to serialize response",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LogoutResponse:
    settings = get_settings()
    refresh_token = request.cookies.get(settings.auth_refresh_cookie_name)

    try:
        if refresh_token:
            token_hash = hash_refresh_token(refresh_token, settings.jwt_secret)
            stmt = select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
            )
            db_refresh_token = (await db.execute(stmt)).scalar_one_or_none()
            if db_refresh_token:
                db_refresh_token.revoked_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception as exc:
        await db.rollback()
        raise _create_error_response(
            "internal_error",
            "Failed to logout",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc

    clear_refresh_cookie(response, settings)
    return LogoutResponse(success=True)


@router.get("/me", response_model=UserSession)
async def get_me(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(get_current_user),
) -> UserSession:
    user = await db.get(User, auth.user_id)
    if user is None:
        raise _create_error_response(
            "internal_error",
            "User not found",
            status.HTTP_404_NOT_FOUND,
        )
    tenant = await db.get(Tenant, user.tenant_id)
    if tenant is None:
        raise _create_error_response(
            "internal_error",
            "Tenant not found",
            status.HTTP_404_NOT_FOUND,
        )
    
    # Получаем scopes на основе роли пользователя (не из БД)
    scopes = get_scopes_for_role(user.role)
    
    # Создаём UserRead с актуальными scopes на основе роли
    user_data = UserRead(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        scopes=scopes,  # Scopes на основе роли, а не из БД
        is_active=user.is_active,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
    
    return UserSession(user=user_data, tenant=TenantRead.model_validate(tenant))
