#!/bin/bash
# Диагностика: почему не работает /api/v1/agents (500, 502).
# Запуск из корня: ./scripts/diagnose-api.sh
#
set -e
cd "$(dirname "$0")/.."

DC="docker compose"
command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
if ! $DC version >/dev/null 2>&1; then DC="docker-compose"; fi

echo "=== 1. Контейнеры ==="
$DC ps -a 2>/dev/null || true

API_Q=$($DC ps -q api 2>/dev/null)
echo ""
echo "=== 2. API: логи (последние 50 строк) ==="
$DC logs api --tail 50 2>/dev/null || echo "(контейнер api не найден или не запущен)"

echo ""
echo "=== 3. Прямой запрос к API (localhost:8000) ==="
CODE=$(curl -s -o /tmp/diag_health.txt -w "%{http_code}" "http://localhost:8000/api/v1/health" 2>/dev/null || echo "000")
echo "GET /api/v1/health -> HTTP $CODE"
if [ "$CODE" = "200" ]; then
  cat /tmp/diag_health.txt | head -1
else
  [ -f /tmp/diag_health.txt ] && cat /tmp/diag_health.txt | head -3
fi

echo ""
CODE_DB=$(curl -s -o /tmp/diag_health_db.txt -w "%{http_code}" "http://localhost:8000/api/v1/health/db" 2>/dev/null || echo "000")
BODY_DB=""
[ -f /tmp/diag_health_db.txt ] && BODY_DB=$(cat /tmp/diag_health_db.txt)
echo "GET /api/v1/health/db -> HTTP $CODE_DB"
echo "$BODY_DB"
rm -f /tmp/diag_health.txt /tmp/diag_health_db.txt

echo ""
echo "=== 4. Entrypoint в контейнере ==="
$DC exec -T api head -8 /app/entrypoint.sh 2>/dev/null || echo "(не удалось выполнить exec)"

echo ""
echo "=== 5. Версия entrypoint на хосте ==="
if [ -f backend/entrypoint.sh ]; then
  grep -E "SKIP_ALEMBIC|run_alembic|WARNING" backend/entrypoint.sh 2>/dev/null | head -3 || head -3 backend/entrypoint.sh
else
  echo "backend/entrypoint.sh не найден"
fi

echo ""
echo "=== Итог ==="
if [ -z "$API_Q" ]; then
  echo "- Контейнер api не запущен — localhost:8000 не отвечает, 502 при запросе через nginx."
  echo "  Запустите: $DC up -d api"
  echo "  Если контейнер сразу падает: $DC logs api --tail 100"
elif [ "$CODE" = "000" ]; then
  echo "- API-контейнер есть, но localhost:8000 не отвечает (код 000)."
  echo "  Проверьте: $DC logs api --tail 80"
elif [ "$CODE_DB" = "200" ] && echo "$BODY_DB" | grep -q '"status":"ok"'; then
  echo "- /health и /health/db OK. Если 502/500 через nginx или front.agentsapp — смотрите конфиг nginx и upstream."
else
  echo "- /health/db: HTTP $CODE_DB или status != ok. Часто: пароль БД, миграции."
  echo "  Запустите: ./scripts/fix-db-and-api.sh"
fi
