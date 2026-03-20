#!/usr/bin/env python3
"""
Быстрая проверка production развертывания
"""

import httpx


def check_endpoint(url: str, description: str) -> bool:
    """Проверяет endpoint и возвращает статус"""
    try:
        response = httpx.get(url, timeout=10)
        if response.status_code == 200:
            print(f"✅ {description}: OK")
            return True
        else:
            print(f"❌ {description}: HTTP {response.status_code}")
            return False
    except httpx.RequestError as e:
        print(f"❌ {description}: {str(e)}")
        return False


def main():
    """Основная функция проверки"""
    base_url = "https://agentsapp.integration-ai.ru"

    print(f"🔍 Проверка production развертывания: {base_url}")
    print("=" * 60)

    # Проверяем основные endpoints
    checks = [
        (f"{base_url}/health", "Базовая проверка здоровья"),
        (f"{base_url}/health/db", "Проверка БД и пула соединений"),
        (f"{base_url}/docs", "Swagger документация"),
        (f"{base_url}/redoc", "ReDoc документация"),
        (f"{base_url}/openapi.json", "OpenAPI схема"),
    ]

    all_ok = True
    for url, description in checks:
        if not check_endpoint(url, description):
            all_ok = False

    print()
    print("=" * 60)

    if all_ok:
        print("🎉 Все проверки пройдены! Production работает корректно.")
    else:
        print("⚠️  Некоторые проверки не пройдены. Проверьте логи приложения.")

    # Дополнительная информация о БД
    try:
        response = httpx.get(f"{base_url}/health/db", timeout=10)
        if response.status_code == 200:
            data = response.json()
            db_info = data.get("database", {})
            print("\n📊 Информация о БД:")
            print(f"   Активных соединений: {db_info.get('active_connections', 'N/A')}")
            print(f"   Использование пула: {db_info.get('usage_percent', 'N/A')}%")
            print(f"   Max соединений: {db_info.get('max_connections', 'N/A')}")
    except httpx.RequestError:
        print("\n⚠️  Не удалось получить информацию о БД")

    print(f"\n🔗 URL для мониторинга: {base_url}/health/db")
    print("📈 Для запуска dashboard: python scripts/db_dashboard.py")
if __name__ == "__main__":
    main()