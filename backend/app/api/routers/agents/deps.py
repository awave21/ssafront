from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent import Agent
from app.schemas.auth import AuthContext


async def get_agent_or_404(agent_id: UUID, db: AsyncSession, user: AuthContext) -> Agent:
    stmt = select(Agent).where(
        Agent.id == agent_id,
        Agent.tenant_id == user.tenant_id,
        Agent.is_deleted.is_(False),
    )
    agent = (await db.execute(stmt)).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent
