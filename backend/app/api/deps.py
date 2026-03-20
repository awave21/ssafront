from __future__ import annotations

from typing import Any, TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import AuthError, decode_token
from app.schemas.auth import AuthContext

T = TypeVar("T")

security = HTTPBearer(auto_error=False)


def _error_response(error_code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": error_code,
            "message": message,
            "detail": message,
            "field_errors": None,
        },
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _error_response(
            "not_authenticated",
            "Not authenticated",
            status.HTTP_401_UNAUTHORIZED,
        )

    try:
        return decode_token(credentials.credentials)
    except AuthError as exc:
        raise _error_response(
            "invalid_token",
            str(exc),
            status.HTTP_401_UNAUTHORIZED,
        ) from exc


def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> AuthContext | None:
    """Опциональная авторизация - возвращает None если нет токена."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None

    try:
        return decode_token(credentials.credentials)
    except AuthError:
        return None


def _has_scope(user_scopes: list[str], scope: str) -> bool:
    """Check if user has scope (exact or wildcard)."""
    if scope in user_scopes:
        return True
    prefix = scope.split(":")[0] + ":*"
    return prefix in user_scopes


def require_scope(scope: str):
    def _checker(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not _has_scope(user.scopes, scope):
            raise _error_response(
                "missing_scope",
                "Missing scope",
                status.HTTP_403_FORBIDDEN,
            )
        return user

    return _checker


def require_scope_any(*scopes: str):
    def _checker(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not any(_has_scope(user.scopes, s) for s in scopes):
            raise _error_response(
                "missing_scope",
                "Missing scope",
                status.HTTP_403_FORBIDDEN,
            )
        return user

    return _checker


def require_role(*roles: str):
    def _checker(user: AuthContext = Depends(get_current_user)) -> AuthContext:
        if user.role not in roles:
            raise _error_response(
                "insufficient_role",
                "Insufficient role",
                status.HTTP_403_FORBIDDEN,
            )
        return user

    return _checker


async def get_or_404(
    db: AsyncSession,
    model: type[T],
    *,
    id: UUID,
    tenant_id: UUID | None = None,
    label: str = "Entity",
    extra_where: list[Any] | None = None,
) -> T:
    """Получить запись по id (и опционально tenant_id) или поднять 404.

    Parameters
    ----------
    db : AsyncSession
    model : SQLAlchemy model class (must have ``id`` column)
    id : primary key value
    tenant_id : if provided, adds ``Model.tenant_id == tenant_id`` filter
    label : human-readable name for the error message
    extra_where : additional SQLAlchemy filter clauses (e.g. ``[Model.is_deleted.is_(False)]``)
    """
    conditions: list[Any] = [model.id == id]  # type: ignore[attr-defined]
    if tenant_id is not None:
        conditions.append(model.tenant_id == tenant_id)  # type: ignore[attr-defined]
    if extra_where:
        conditions.extend(extra_where)

    stmt = select(model).where(*conditions)
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{label} not found",
        )
    return row
