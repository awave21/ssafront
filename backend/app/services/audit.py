from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditLog
from app.schemas.auth import AuthContext


async def write_audit(
    session: AsyncSession,
    user: AuthContext,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit = AuditLog(
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_=metadata,
    )
    session.add(audit)
    await session.commit()
