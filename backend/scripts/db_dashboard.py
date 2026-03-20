#!/usr/bin/env python3
"""
Dashboard для мониторинга состояния БД и пула соединений
"""

import asyncio
import httpx
import os
from datetime import datetime


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header():
    """Печатает заголовок dashboard"""
    print("\n" + "="*70)
    print(f"{Colors.BOLD}🚀 DATABASE CONNECTION DASHBOARD{Colors.END}")
    print("="*70)
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


def print_metric(label: str, value: str, status: str = "info"):
    """Печатает метрику с цветовым кодированием"""
    colors = {
        "good": Colors.GREEN,
        "warning": Colors.YELLOW,
        "error": Colors.RED,
        "info": Colors.BLUE
    }
    color = colors.get(status, Colors.BLUE)
    label_text = f"{label:<28}"
    print(f"{label_text} {color}{value}{Colors.END}")


def get_status_for_percentage(percentage: float) -> str:
    """Определяет статус на основе процента использования"""
    if percentage > 90:
        return "error"
    elif percentage > 75:
        return "warning"
    else:
        return "good"


async def fetch_health_data(base_url: str) -> dict:
    """Получает данные о здоровье API"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{base_url}/health/db")
            if response.status_code == 200:
                return response.json()
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def load_env_config():
    """Загружает настройки из .env файла"""
    config = {}
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")

    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, _, value = line.partition('=')
                    if key and value:
                        config[key] = value.strip('"').strip("'")

    return config


async def main():
    """Основная функция dashboard"""
    base_url = os.getenv("API_URL", "https://agentsapp.integration-ai.ru")
    refresh_interval = int(os.getenv("REFRESH_INTERVAL", "5"))

    # Загружаем конфигурацию
    env_config = load_env_config()

    print("Настройки пула из .env:")
    print(f"  DB_POOL_SIZE: {env_config.get('DB_POOL_SIZE', '20 (default)')}")
    print(f"  DB_MAX_OVERFLOW: {env_config.get('DB_MAX_OVERFLOW', '30 (default)')}")
    print(f"  POSTGRES_MAX_CONNECTIONS: {env_config.get('POSTGRES_MAX_CONNECTIONS', '200 (docker default)')}")
    print()

    while True:
        try:
            # Получаем данные
            health_data = await fetch_health_data(base_url)

            print_header()

            if "error" in health_data:
                print_metric("Статус API", f"❌ Ошибка: {health_data['error']}", "error")
            else:
                db_info = health_data.get("database", {})

                # Основные метрики
                active = db_info.get("active_connections", 0)
                total = db_info.get("total_connections", 0)
                max_conn = db_info.get("max_connections", 0)
                usage = db_info.get("usage_percent", 0)

                pool_config = db_info.get("pool_config", {})
                pool_size = pool_config.get("pool_size", 20)
                max_overflow = pool_config.get("max_overflow", 30)
                total_pool_capacity = pool_config.get("total_pool_capacity", 50)

                # Определяем статусы
                usage_status = get_status_for_percentage(usage)
                pool_status = "good" if active <= total_pool_capacity else "warning"

                # Выводим метрики
                print_metric("Статус API", "✅ OK", "good")
                print_metric("Активных соединений", str(active), usage_status)
                print_metric("Всего соединений", str(total), "info")
                print_metric("Max соединений (PostgreSQL)", str(max_conn), "info")
                print_metric("Использование пула", f"{usage}%", usage_status)
                print()
                print_metric("Размер пула (pool_size)", str(pool_size), "info")
                print_metric("Max overflow", str(max_overflow), "info")
                print_metric("Общая емкость пула", str(total_pool_capacity), pool_status)

                # Предупреждения
                warnings = []
                if usage > 80:
                    warnings.append(f"⚠️  Высокая загрузка: {usage}% соединений используется")
                if active > total_pool_capacity:
                    warnings.append("⚠️  Превышена емкость пула соединений!")

                if warnings:
                    print("\n" + Colors.YELLOW + "ВНИМАНИЕ:" + Colors.END)
                    for warning in warnings:
                        print(f"  {warning}")

            print(f"\nОбновление каждые {refresh_interval} секунд... (Ctrl+C для выхода)")
            await asyncio.sleep(refresh_interval)

        except KeyboardInterrupt:
            print("\n\n👋 Выход из dashboard")
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}")
            print(f"Повторная попытка через {refresh_interval} секунд...")
            await asyncio.sleep(refresh_interval)


if __name__ == "__main__":
    print("Database Connection Dashboard")
    print("Примеры использования:")
    print("  python db_dashboard.py                                    # production домен")
    print("  API_URL=http://localhost:8000 python db_dashboard.py   # локальная разработка")
    print("  REFRESH_INTERVAL=2 python db_dashboard.py              # обновление каждые 2 сек")
    print("-" * 50)

    asyncio.run(main())