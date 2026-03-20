#!/usr/bin/env python3
"""
Скрипт для тестирования нагрузки на БД и мониторинга пула соединений
"""

import asyncio
import httpx
import time
import sys


async def make_request(client: httpx.AsyncClient, url: str) -> dict:
    """Выполнить один запрос к API"""
    try:
        response = await client.get(url)
        return {
            "status": response.status_code,
            "url": url,
            "error": None,
        }
    except Exception as e:
        return {
            "status": None,
            "url": url,
            "error": str(e),
        }


async def check_db_health(client: httpx.AsyncClient, base_url: str) -> dict:
    """Проверить состояние БД"""
    url = f"{base_url}/health/db"
    try:
        response = await client.get(url)
        if response.status_code == 200:
            return response.json()
        return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def run_load_test(base_url: str, concurrent_requests: int, duration_seconds: int):
    """Запустить тест нагрузки"""
    print(f"🚀 Запуск теста нагрузки: {concurrent_requests} параллельных запросов, {duration_seconds} секунд")
    print(f"   API URL: {base_url}")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=10) as client:
        start_time = time.time()
        request_count = 0
        errors = 0

        # Создаем задачи для параллельных запросов
        tasks = []

        # Запускаем нагрузку
        while time.time() - start_time < duration_seconds:
            # Очищаем завершенные задачи
            tasks = [t for t in tasks if not t.done()]

            # Добавляем новые задачи, если не превышен лимит
            while len(tasks) < concurrent_requests:
                task = asyncio.create_task(make_request(client, f"{base_url}/health/db"))
                tasks.append(task)

            # Ждем немного
            await asyncio.sleep(0.1)

            # Подсчитываем результаты
            completed_tasks = [t for t in tasks if t.done()]
            for task in completed_tasks:
                result = task.result()
                request_count += 1
                if result.get("error") or result.get("status") != 200:
                    errors += 1

                # Каждые 10 запросов показываем статус
                if request_count % 10 == 0:
                    # Проверяем состояние БД
                    health_data = await check_db_health(client, base_url)
                    if "database" in health_data:
                        db_info = health_data["database"]
                        print(f"📊 Запросов: {request_count} | "
                              f"Активных соединений: {db_info.get('active_connections', 'N/A')} | "
                              f"Использование: {db_info.get('usage_percent', 'N/A')}% | "
                              f"Ошибок: {errors}")

        # Финальная статистика
        total_time = time.time() - start_time
        rps = request_count / total_time

        print("-" * 60)
        print("📈 Результаты теста:")
        print(f"   Время теста: {total_time:.2f} сек")
        print(f"   Всего запросов: {request_count}")
        print(f"   Ошибок: {errors}")
        print(f"   RPS (запросов в секунду): {rps:.1f}")

        # Финальная проверка БД
        final_health = await check_db_health(client, base_url)
        if "database" in final_health:
            db_info = final_health["database"]
            print(f"   Финальное состояние БД:")
            print(f"   - Активных соединений: {db_info.get('active_connections', 'N/A')}")
            print(f"   - Всего соединений: {db_info.get('total_connections', 'N/A')}")
            print(f"   - Max соединений: {db_info.get('max_connections', 'N/A')}")
            print(f"   - Использование: {db_info.get('usage_percent', 'N/A')}%")


def main():
    if len(sys.argv) != 4:
        print("Использование: python load_test_db.py <base_url> <concurrent_requests> <duration_seconds>")
        print("Примеры:")
        print("  python load_test_db.py https://agentsapp.integration-ai.ru 20 30")
        print("  python load_test_db.py http://localhost:8000 10 15")
        sys.exit(1)

    base_url = sys.argv[1]
    concurrent_requests = int(sys.argv[2])
    duration_seconds = int(sys.argv[3])

    asyncio.run(run_load_test(base_url, concurrent_requests, duration_seconds))


if __name__ == "__main__":
    main()