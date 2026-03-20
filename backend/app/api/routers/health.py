from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """Базовая проверка здоровья сервиса (без зависимостей от БД)"""
    return {"status": "ok"}


@router.get("/health/db")
async def db_health(db: AsyncSession = Depends(get_db)) -> dict:
    """Проверка здоровья базы данных и пула соединений"""
    try:
        settings = get_settings()

        # Проверяем соединение (без чтения результатов)
        await db.execute(text("SELECT 1"))

        # Получаем информацию о соединениях
        active_result = await db.execute(text("""
            SELECT count(*) as active_connections
            FROM pg_stat_activity
            WHERE state = 'active'
        """))
        active_count = active_result.scalar()

        total_result = await db.execute(text("""
            SELECT count(*) as total_connections
            FROM pg_stat_activity
        """))
        total_count = total_result.scalar()

        max_result = await db.execute(text("SHOW max_connections"))
        max_connections = int(max_result.scalar())

        # Вычисляем использование
        usage_percent = round((active_count / max_connections) * 100, 1) if max_connections else 0

        return {
            "status": "ok",
            "database": {
                "active_connections": active_count,
                "total_connections": total_count,
                "max_connections": max_connections,
                "usage_percent": usage_percent,
                "pool_config": {
                    "pool_size": settings.db_pool_size,
                    "max_overflow": settings.db_max_overflow,
                    "total_pool_capacity": settings.db_pool_size + settings.db_max_overflow,
                },
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "database": {
                "error": str(e)
            }
        }
