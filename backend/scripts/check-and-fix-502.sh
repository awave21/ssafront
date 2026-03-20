#!/bin/bash
# Скрипт для диагностики и исправления ошибки 502 Bad Gateway
# Использование: ./scripts/check-and-fix-502.sh

set -e
cd "$(dirname "$0")/.."

DC="docker compose"
if ! $DC version >/dev/null 2>&1; then
  DC="docker-compose"
fi

echo "=== Диагностика ошибки 502 Bad Gateway ==="
echo ""

echo "[1/7] Проверка статуса Docker контейнеров..."
if ! $DC ps >/dev/null 2>&1; then
  echo "⚠ Ошибка: не удается выполнить docker compose."
  echo "Проверьте права доступа или запустите с sudo"
  exit 1
fi

$DC ps

echo ""
echo "[2/7] Проверка API контейнера..."
API_STATUS=$($DC ps api --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "not_running")
if [ "$API_STATUS" != "running" ]; then
  echo "⚠ API контейнер не запущен (статус: $API_STATUS)"
  echo "Запускаю API контейнер..."
  $DC up -d api
  echo "Ожидание запуска (20 секунд)..."
  sleep 20
else
  echo "✓ API контейнер запущен"
  echo "Перезапускаю для надежности..."
  $DC restart api
  sleep 10
fi

echo ""
echo "[3/7] Проверка порта 8000..."
if curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/health" 2>/dev/null | grep -q "200"; then
  echo "✓ API отвечает на порту 8000"
else
  echo "✗ API не отвечает на порту 8000"
  echo ""
  echo "Последние логи API:"
  $DC logs api --tail 50
  echo ""
  echo "⚠ Проблема: API контейнер не может запуститься или не слушает порт 8000"
  echo "Проверьте:"
  echo "  - $DC logs api --tail 100"
  echo "  - $DC logs db --tail 50"
  echo "  - Проверьте .env файл"
  exit 1
fi

echo ""
echo "[4/7] Проверка nginx контейнера..."
NGINX_STATUS=$($DC ps nginx --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4 || echo "not_running")
if [ "$NGINX_STATUS" != "running" ]; then
  echo "⚠ Nginx контейнер не запущен (статус: $NGINX_STATUS)"
  echo "Запускаю nginx контейнер..."
  $DC up -d nginx
  sleep 5
else
  echo "✓ Nginx контейнер запущен"
fi

echo ""
echo "[5/7] Проверка nginx на хосте..."
if pgrep -x nginx > /dev/null; then
  echo "✓ Nginx процесс запущен на хосте"
  echo "⚠ Внимание: Nginx запущен и на хосте, и в контейнере"
  echo "Проверьте конфигурацию для front.agentsapp.integration-ai.ru"
else
  echo "ℹ Nginx не запущен на хосте (используется только контейнер)"
fi

echo ""
echo "[6/7] Проверка доступности API через nginx контейнер..."
NGINX_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost/api/v1/health" 2>/dev/null || echo "000")
if [ "$NGINX_HEALTH" = "200" ]; then
  echo "✓ Nginx успешно проксирует запросы к API"
else
  echo "✗ Nginx не может достучаться до API (HTTP $NGINX_HEALTH)"
  echo ""
  echo "Логи nginx контейнера:"
  $DC logs nginx --tail 30
fi

echo ""
echo "[7/7] Финальная проверка..."
echo "Проверка /api/v1/health:"
curl -s "http://localhost:8000/api/v1/health" | head -3
echo ""

echo "=== Резюме ==="
echo ""
echo "Если ошибка 502 сохраняется:"
echo ""
echo "1. Проверьте логи API:"
echo "   $DC logs api --tail 100"
echo ""
echo "2. Проверьте логи nginx:"
echo "   $DC logs nginx --tail 50"
echo ""
echo "3. Проверьте подключение к БД:"
echo "   $DC logs db --tail 50"
echo ""
echo "4. Проверьте конфигурацию nginx для front.agentsapp.integration-ai.ru"
echo "   (может быть отдельный nginx на хосте)"
echo ""
echo "5. Перезапустите все контейнеры:"
echo "   $DC restart"
