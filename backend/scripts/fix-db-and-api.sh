#!/bin/bash
# Устраняет 500 на GET /api/v1/agents. Причины: пароль БД != postgres ИЛИ миграции не применены.
#
# Запуск из КОРНЯ проекта (где docker-compose.yml), контейнеры должны быть подняты:
#   cd /root/agentsapp   # или ваш путь
#   ./scripts/fix-db-and-api.sh
#
# Если используете docker-compose (v1): замените "docker compose" на "docker-compose".
set -e
cd "$(dirname "$0")/.."

DC="docker compose"
if ! $DC version >/dev/null 2>&1; then
  DC="docker-compose"
fi

echo "[1/5] Проверка контейнеров..."
if ! $DC ps -q db >/dev/null 2>&1 || ! $DC ps -q api >/dev/null 2>&1; then
  echo "Ошибка: контейнеры db или api не запущены. Выполните: $DC up -d"
  exit 1
fi

echo "[2/5] Сброс пароля postgres в БД (на postgres для совпадения с DATABASE_URL)..."
$DC exec -T db psql -U postgres -d postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"

echo "[3/5] Применение миграций Alembic (добавляет max_history_messages, sqns_*, session_messages и т.д.)..."
$DC exec -T api alembic -c /app/alembic.ini upgrade head

echo "[4/5] Перезапуск API (сброс пула соединений)..."
$DC restart api

echo "[5/5] Ожидание запуска API и проверка /api/v1/health/db..."
sleep 5
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/health/db" 2>/dev/null || true)
if [ "$HEALTH" = "200" ]; then
  BODY=$(curl -s "http://localhost:8000/api/v1/health/db" 2>/dev/null || true)
  if echo "$BODY" | grep -q '"status":"ok"'; then
    echo "  /api/v1/health/db: OK (status=ok)"
  else
    echo "  /api/v1/health/db: 200, но status != ok. Ответ: $BODY"
  fi
else
  echo "  /api/v1/health/db: HTTP $HEALTH (проверьте: curl -s http://localhost:8000/api/v1/health/db)"
fi

echo ""
echo "Готово. Проверка agents:"
echo "  curl -s -H 'Authorization: Bearer <токен>' http://localhost:8000/api/v1/agents"
echo ""
echo "Если 500 на /api/v1/agents: $DC logs api --tail 100"
