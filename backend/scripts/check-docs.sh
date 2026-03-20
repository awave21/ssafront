#!/usr/bin/env bash
# Проверка доступности API и Swagger docs
# Использование: ./scripts/check-docs.sh [BASE_URL]
# По умолчанию: https://agentsapp.integration-ai.ru

set -e
BASE="${1:-https://agentsapp.integration-ai.ru}"

echo "=== Проверка $BASE ==="
echo ""

echo "1. Корень API (GET /):"
curl -sS -o /dev/null -w "   HTTP %{http_code}, время %{time_total}s\n" --connect-timeout 10 "$BASE/" || echo "   Ошибка: недоступен"
echo ""

echo "2. OpenAPI schema (GET /openapi.json):"
curl -sS -o /dev/null -w "   HTTP %{http_code}, время %{time_total}s\n" --connect-timeout 10 "$BASE/openapi.json" || echo "   Ошибка: недоступен"
echo ""

echo "3. Swagger UI (GET /docs):"
curl -sS -o /dev/null -w "   HTTP %{http_code}, время %{time_total}s\n" --connect-timeout 15 "$BASE/docs" || echo "   Ошибка: недоступен"
echo ""

echo "4. ReDoc (GET /redoc):"
curl -sS -o /dev/null -w "   HTTP %{http_code}, время %{time_total}s\n" --connect-timeout 15 "$BASE/redoc" || echo "   Ошибка: недоступен"
echo ""

echo "Готово. Если все 200 — API и документация доступны."
