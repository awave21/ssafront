from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.exc import OperationalError, DisconnectionError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.utils.debug_logging import emit_debug_log


def create_engine() -> tuple[async_sessionmaker[AsyncSession], str]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,  # Проверяет соединение перед использованием
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        pool_recycle=settings.db_pool_recycle_seconds,
        # Дополнительные настройки для устойчивости соединений
        echo=False,  # Логирование SQL (можно включить для отладки)
        future=True,  # Использовать новый API SQLAlchemy 2.0
    )

    # Кодек pgvector для asyncpg здесь НЕ регистрируется намеренно.
    #
    # register_vector нужен, когда с базой работают сырым asyncpg. У нас работает
    # SQLAlchemy, и тип pgvector.sqlalchemy.Vector сам сериализует вектор для
    # драйвера — в строку вида "[0.1,0.2]". Кодек же ждёт список и такую строку
    # отвергает: вместе они кодируют дважды.
    #
    # Пока кодек был зарегистрирован, ЛЮБАЯ запись вектора через модель падала с
    # asyncpg DataError: expected list or ndarray. Молча, потому что вызовы
    # обёрнуты в try/except: новая карточка прямых вопросов оставалась без
    # эмбеддинга, документ базы знаний — без чанков, детектор пропущенных звонков
    # всегда возвращал None. Отсюда же двойные касты CAST(CAST(:x AS text) AS vector)
    # по всему коду — их писали, обходя этот самый конфликт.
    #
    # Проверено на проде до правки: INSERT и UPDATE вектора падали, без кодека —
    # проходят; поиск и чтение вектора работают одинаково в обоих случаях.

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    # region agent log
    emit_debug_log(
        location="backend/app/db/session.py:create_engine",
        message="engine configured",
        data={
            "driver": engine.url.drivername,
            "host": engine.url.host,
            "port": engine.url.port,
            "database": engine.url.database,
        },
        hypothesisId="H1",
    )
    # endregion
    return session_factory, settings.database_url


async_session_factory, database_url = create_engine()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Создает сессию БД. pool_pre_ping=True автоматически проверяет соединения перед использованием."""
    # region agent log
    emit_debug_log(
        location="backend/app/db/session.py:get_db",
        message="get_db called, creating session",
        data={},
        hypothesisId="H2",
    )
    # endregion
    try:
        async with async_session_factory() as session:
            # region agent log
            emit_debug_log(
                location="backend/app/db/session.py:get_db",
                message="session created successfully",
                data={},
                hypothesisId="H2",
            )
            # endregion
            try:
                yield session
            except (OperationalError, DisconnectionError) as exc:
                # Если ошибка произошла во время использования сессии,
                # логируем и пробуем откатить транзакцию
                emit_debug_log(
                    location="backend/app/db/session.py:get_db",
                    message="database error during session use, attempting rollback",
                    data={
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                    hypothesisId="H2",
                )
                try:
                    await session.rollback()
                except Exception:
                    pass  # Игнорируем ошибки при rollback
                raise
    except Exception as exc:
        # region agent log
        emit_debug_log(
            location="backend/app/db/session.py:get_db",
            message="session creation failed",
            data={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
            },
            hypothesisId="H2",
        )
        # endregion
        raise
