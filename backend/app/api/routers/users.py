from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_scope
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.user import UserRead

router = APIRouter()


class UserRoleUpdate(BaseModel):
    role: str = Field(..., pattern="^(admin|manager)$")


@router.get("", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_scope("users:read")),
) -> list[UserRead]:
    stmt = (
        select(User)
        .where(User.tenant_id == auth.tenant_id, User.is_active.is_(True))
        .order_by(User.created_at.asc())
    )
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [UserRead.model_validate(u) for u in users]


@router.patch("/{user_id}/role", response_model=UserRead)
async def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_scope("users:manage")),
) -> UserRead:
    user = await db.get(User, user_id)
    if not user or user.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change owner role",
        )

    from app.services.users import resolve_scopes

    user.role = payload.role
    user.scopes = resolve_scopes(payload.role, None)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(require_scope("users:manage")),
) -> None:
    tenant = await db.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    if tenant.owner_user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot remove organization owner",
        )

    user = await db.get(User, user_id)
    if not user or user.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.commit()
    return None
