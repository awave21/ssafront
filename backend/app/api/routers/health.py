from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.services.runtime.neo4j_client import get_neo4j_driver

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


@router.get("/health/neo4j")
async def neo4j_health() -> dict:
    """Проверка доступности Neo4j драйвера/соединения."""
    settings = get_settings()
    if not settings.neo4j_enabled:
        return {
            "status": "disabled",
            "neo4j": {
                "enabled": False,
            },
        }

    driver = get_neo4j_driver()
    if driver is None:
        return {
            "status": "error",
            "neo4j": {
                "enabled": True,
                "available": False,
                "error": "driver_not_initialized",
            },
        }

    try:
        database = settings.neo4j_database or None
        with driver.session(database=database) as session:
            session.run("RETURN 1 AS ok").single()
        return {
            "status": "ok",
            "neo4j": {
                "enabled": True,
                "available": True,
                "database": database or "default",
            },
        }
    except Exception as exc:
        return {
            "status": "error",
            "neo4j": {
                "enabled": True,
                "available": False,
                "database": settings.neo4j_database or "default",
                "error": str(exc),
            },
        }
