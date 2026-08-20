"""Проверка каналов Jivo в базе данных"""
import asyncio
import os
import sys
from pathlib import Path

# Добавляем корень backend в PYTHONPATH
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.db.models.channel import Channel


async def main():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@db:5432/agents")
    engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        stmt = (
            select(Channel)
            .where(Channel.type == "jivo", Channel.is_deleted.is_(False))
            .order_by(Channel.created_at)
        )
        result = await db.execute(stmt)
        channels = result.scalars().all()

        if not channels:
            print("❌ Не найдено активных каналов Jivo")
            return

        print(f"✅ Найдено активных каналов Jivo: {len(channels)}\n")
        
        for idx, ch in enumerate(channels, 1):
            print(f"{'='*80}")
            print(f"Канал #{idx}")
            print(f"{'='*80}")
            print(f"ID:                    {ch.id}")
            print(f"Тип:                   {ch.type}")
            print(f"Provider Token:        {ch.jivo_provider_token}")
            print(f"Provider ID:           {ch.jivo_provider_id}")
            print(f"Reply Base URL:        {ch.jivo_reply_base_url}")
            print(f"Создан:                {ch.created_at}")
            print(f"Обновлён:              {ch.updated_at}")
            
            # Формируем webhook URL как в коде
            from app.core.config import get_settings
            settings = get_settings()
            
            if ch.jivo_provider_token:
                endpoint = f"{settings.api_prefix}/webhooks/jivo/{ch.jivo_provider_token}"
                base_url = (settings.public_base_url or "").rstrip("/")
                webhook_url = f"{base_url}{endpoint}"
                print(f"\n📍 Webhook URL (расчётный):")
                print(f"   {webhook_url}")
            
            print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
