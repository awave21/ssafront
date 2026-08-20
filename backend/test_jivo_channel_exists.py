#!/usr/bin/env python3
"""Простая проверка наличия канала Jivo по токену"""
import os
import sys
import asyncio
import asyncpg

TOKEN = "CAJLGey0-s4-2Af_T1HpEnmCVZgkxh7aBZHfrpCwiB8"

async def main():
    # Получаем DATABASE_URL из .env или используем дефолт
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agents_dev")
    
    # Парсим URL
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    db_url = db_url.replace("@db:", "@localhost:")
    
    print(f"Подключаемся к БД: {db_url.replace('postgres:postgres', 'postgres:***')}")
    
    try:
        conn = await asyncpg.connect(db_url)
        print("✅ Подключение успешно")
        
        # Проверяем каналы Jivo
        query = """
        SELECT id, name, type, jivo_provider_token, jivo_provider_id, jivo_reply_base_url, is_deleted
        FROM channels
        WHERE type = 'jivo' AND is_deleted = false
        """
        
        rows = await conn.fetch(query)
        print(f"\n📊 Найдено активных Jivo каналов: {len(rows)}\n")
        
        found_token = False
        for row in rows:
            print(f"Channel ID: {row['id']}")
            print(f"  Name: {row['name']}")
            print(f"  Token: {row['jivo_provider_token']}")
            print(f"  Provider ID: {row['jivo_provider_id']}")
            print(f"  Reply URL: {row['jivo_reply_base_url']}")
            print()
            
            if row['jivo_provider_token'] == TOKEN:
                found_token = True
                print(f"✅ НАЙДЕН канал с нужным токеном!")
                print(f"   Webhook endpoint: https://api.chatmedbot.ru/api/v1/webhooks/jivo/{TOKEN}")
                print()
        
        if not found_token and len(rows) > 0:
            print(f"❌ Канал с токеном {TOKEN[:20]}... НЕ НАЙДЕН")
            print(f"   Возможно, скрипт fix_jivo_single_agent.sql не был выполнен")
        elif len(rows) == 0:
            print(f"⚠️  В БД вообще нет активных Jivo каналов")
            print(f"   Нужно создать канал или выполнить SQL скрипт")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
