from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_refresh_token
from app.db.models.invitation import Invitation
from app.services.users import normalize_email


def hash_invite_token(token: str, pepper: str) -> str:
    return hash_refresh_token(token, pepper)


async def get_invitation_by_token(db: AsyncSession, token: str, pepper: str) -> Invitation | None:
    token_hash = hash_invite_token(token, pepper)
    stmt = select(Invitation).where(
        Invitation.token_hash == token_hash,
        Invitation.expires_at > datetime.now(timezone.utc),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
