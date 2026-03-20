#!/bin/bash
# Скрипт для перезапуска API контейнера
# Использование: ./scripts/restart-api.sh

set -e
cd "$(dirname "$0")/.."

DC="docker compose"
if ! $DC version >/dev/null 2>&1; then
  DC="docker-compose"
fi

echo "=== Диагностика и перезапуск API ==="
echo ""

echo "[1/6] Проверка статуса контейнеров..."
if ! $DC ps >/dev/null 2>&1; then
  echo "⚠ Ошибка: не удается выполнить docker compose. Проверьте права доступа."
  echo "Попробуйте: sudo $DC ps"
  exit 1
fi

$DC ps

echo ""
echo "[2/6] Проверка, запущен ли API контейнер..."
API_RUNNING=$($DC ps -q api 2>/dev/null | wc -l)
if [ "$API_RUNNING" = "0" ]; then
  echo "⚠ API контейнер не запущен. Запускаю..."
  $DC up -d api
  echo "Ожидание запуска (15 секунд)..."
  sleep 15
else
  echo "[3/6] Перезапуск API контейнера..."
  $DC restart api
  echo "Ожидание запуска (10 секунд)..."
  sleep 10
fi

echo ""
echo "[4/6] Проверка health endpoint напрямую..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/health" 2>/dev/null || echo "000")
if [ "$HEALTH" = "200" ]; then
  echo "✓ API работает (HTTP 200)"
  curl -s "http://localhost:8000/api/v1/health" | head -3
else
  echo "✗ API не отвечает (HTTP $HEALTH)"
  echo ""
  echo "Проверка логов API (последние 50 строк):"
  $DC logs api --tail 50
  echo ""
  echo "⚠ Если проблема сохраняется, проверьте:"
  echo "  - $DC logs api --tail 100"
  echo "  - $DC logs db --tail 50"
  echo "  - Проверьте .env файл и переменные DATABASE_URL"
fi

echo ""
echo "[5/6] Проверка nginx контейнера..."
NGINX_RUNNING=$($DC ps -q nginx 2>/dev/null | wc -l)
if [ "$NGINX_RUNNING" = "0" ]; then
  echo "⚠ Nginx контейнер не запущен. Запускаю..."
  $DC up -d nginx
  sleep 5
fi

echo ""
echo "[6/6] Проверка через nginx..."
NGINX_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/api/v1/health" 2>/dev/null || echo "000")
if [ "$NGINX_STATUS" = "200" ]; then
  echo "✓ Nginx проксирует запросы успешно"
else
  echo "✗ Nginx не может достучаться до API (HTTP $NGINX_STATUS)"
  echo ""
  echo "Проверка логов nginx (последние 30 строк):"
  $DC logs nginx --tail 30
fi

echo ""
echo "=== Готово ==="
echo ""
echo "Если проблема сохраняется:"
echo "  1. Проверьте логи: $DC logs api --tail 100"
echo "  2. Проверьте БД: $DC logs db --tail 50"
echo "  3. Проверьте конфигурацию: cat .env | grep DATABASE_URL"
echo "  4. Перезапустите все: $DC restart"
