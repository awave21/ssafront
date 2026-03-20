#!/bin/bash
# Скрипт для применения миграции refresh_tokens

set -e

echo "Применение миграции refresh_tokens..."

# Проверяем, что мы в правильной директории
if [ ! -f "docker-compose.yml" ]; then
    echo "Ошибка: docker-compose.yml не найден. Запустите скрипт из корневой директории проекта."
    exit 1
fi

# Применяем миграцию
echo "Применяем миграцию через Docker..."
docker compose exec -T api alembic upgrade head

echo "Миграция применена успешно!"
echo ""
echo "Проверка таблицы refresh_tokens..."
docker compose exec -T api python -c "
import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def check_table():
    async with async_session_factory() as session:
        result = await session.execute(text('SELECT COUNT(*) FROM refresh_tokens'))
        count = result.scalar()
        print(f'Таблица refresh_tokens существует. Записей: {count}')

asyncio.run(check_table())
"

echo ""
echo "Готово! Refresh token теперь поддерживается."
