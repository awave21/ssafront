#!/usr/bin/env python3
"""
Тестовый скрипт для проверки обработки Jivo webhook.
Отправляет тестовый CLIENT_MESSAGE webhook на локальный endpoint.
"""
import json
import sys
from pathlib import Path

# Добавляем путь к приложению
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

# Токен из конфигурации Jivo (05.08.2026)
TOKEN = "CAJLGey0-s4-2Af_T1HpEnmCVZgkxh7aBZHfrpCwiB8"

# Тестовое событие CLIENT_MESSAGE от Jivo
TEST_EVENT = {
    "id": "test_event_001",
    "event_name": "CLIENT_MESSAGE",
    "client_id": "test_client_12345",
    "chat_id": "test_chat_67890",
    "site_id": "testsite",
    "message": {
        "type": "TEXT",
        "text": "Тестовое сообщение от Светланы из Jivo Support",
        "timestamp": 1722853200
    },
    "user": {
        "name": "Светлана",
        "email": "svetlana@jivo.ru",
        "phone": "+79991234567"
    }
}


async def test_webhook():
    """Отправить тестовый webhook на локальный endpoint"""
    url = f"http://localhost:8000/api/v1/webhooks/jivo/{TOKEN}"
    
    print(f"Отправка тестового webhook на {url}")
    print(f"Событие: {json.dumps(TEST_EVENT, ensure_ascii=False, indent=2)}")
    print("-" * 80)
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                url,
                json=TEST_EVENT,
                headers={"Content-Type": "application/json"}
            )
            
            print(f"✅ Статус: {response.status_code}")
            print(f"Ответ: {response.text}")
            
            if response.status_code == 200:
                print("\n✅ Webhook успешно обработан!")
                print("Проверьте логи в backend/logs/webhooks.log")
            else:
                print(f"\n❌ Ошибка: {response.status_code}")
                
        except Exception as e:
            print(f"\n❌ Исключение: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_webhook())
