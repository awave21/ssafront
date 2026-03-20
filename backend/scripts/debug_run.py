import asyncio
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd() + "/backend")

from app.db.session import async_session_factory
from app.db.models.run import Run
from sqlalchemy import select

async def check():
    trace_id = "cda59405-2314-4e87-933e-7b137850bf25"
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agents")
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        stmt = select(Run).where(Run.trace_id == trace_id)
        res = await db.execute(stmt)
        run = res.scalar_one_or_none()
        if run:
            print(f"Status: {run.status}")
            print(f"Error: {run.error_message}")
            print(f"Input: {run.input_message}")
            print(f"Output: {run.output_message}")
        else:
            print(f"Run with trace_id {trace_id} not found")

if __name__ == "__main__":
    asyncio.run(check())
