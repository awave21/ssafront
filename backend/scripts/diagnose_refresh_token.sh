#!/bin/bash
# Диагностика проблем с refresh token

set -e

echo "=== Диагностика refresh token ==="
echo ""

# Проверка 1: Существует ли таблица refresh_tokens
echo "1. Проверка существования таблицы refresh_tokens..."
docker compose exec -T api python -c "
import asyncio
from sqlalchemy import text
from app.db.session import async_session_factory

async def check_table():
    try:
        async with async_session_factory() as session:
            result = await session.execute(text(\"SELECT COUNT(*) FROM refresh_tokens\"))
            count = result.scalar()
            print(f'   ✓ Таблица существует. Записей: {count}')
            if count == 0:
                print('   ⚠ ВНИМАНИЕ: Таблица пуста! Refresh token не сохраняются.')
            return True
    except Exception as e:
        print(f'   ✗ ОШИБКА: {e}')
        print('   ⚠ Таблица refresh_tokens не существует!')
        print('   Решение: Примените миграцию: docker compose exec api alembic upgrade head')
        return False

asyncio.run(check_table())
" 2>&1 || echo "   ✗ Не удалось подключиться к БД"

echo ""
echo "2. Проверка последних refresh token в БД..."
docker compose exec -T api python -c "
import asyncio
from sqlalchemy import text
from app.db.session import async_session_factory

async def check_tokens():
    try:
        async with async_session_factory() as session:
            result = await session.execute(text(\"\"\"
                SELECT user_id, created_at, expires_at, revoked_at 
                FROM refresh_tokens 
                ORDER BY created_at DESC 
                LIMIT 5
            \"\"\"))
            rows = result.fetchall()
            if rows:
                print('   Последние 5 refresh token:')
                for row in rows:
                    revoked = 'ОТОЗВАН' if row[3] else 'АКТИВЕН'
                    print(f'   - User: {row[0]}, Создан: {row[1]}, Истекает: {row[2]}, Статус: {revoked}')
            else:
                print('   ⚠ Нет записей в таблице refresh_tokens')
    except Exception as e:
        print(f'   ✗ ОШИБКА: {e}')

asyncio.run(check_tokens())
" 2>&1 || echo "   ✗ Не удалось получить данные"

echo ""
echo "3. Проверка миграций..."
docker compose exec -T api alembic current 2>&1 | head -5 || echo "   ✗ Не удалось проверить миграции"

echo ""
echo "=== Конец диагностики ==="
