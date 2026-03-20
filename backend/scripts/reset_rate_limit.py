#!/usr/bin/env python3
"""Скрипт для сброса rate limit в Redis для регистрации."""

import sys
import os

# Добавляем путь к backend для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.config import get_settings
import redis

def reset_rate_limit_for_ip(ip_address: str = None):
    """Сбрасывает rate limit для указанного IP или всех."""
    settings = get_settings()
    
    if not settings.redis_url:
        print("Redis URL не настроен. Rate limit не используется.")
        return
    
    try:
        r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        
        # Ищем все ключи rate limiter
        pattern = "LIMITER:*"
        if ip_address:
            pattern = f"LIMITER:*{ip_address}*"
        
        keys = r.keys(pattern)
        
        if not keys:
            print(f"Ключи rate limit не найдены для паттерна: {pattern}")
            return
        
        print(f"Найдено ключей: {len(keys)}")
        for key in keys:
            print(f"  - {key}")
        
        # Удаляем все найденные ключи
        deleted = r.delete(*keys)
        print(f"\nУдалено ключей: {deleted}")
        print("Rate limit сброшен успешно!")
        
    except Exception as e:
        print(f"Ошибка при сбросе rate limit: {e}")
        sys.exit(1)


if __name__ == "__main__":
    ip = sys.argv[1] if len(sys.argv) > 1 else None
    if ip:
        print(f"Сброс rate limit для IP: {ip}")
    else:
        print("Сброс всех rate limits (используйте IP как аргумент для конкретного IP)")
    
    reset_rate_limit_for_ip(ip)
