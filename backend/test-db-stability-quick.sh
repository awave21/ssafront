#!/bin/bash
# Быстрая проверка стабильности БД (без полных перезапусков)

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "Quick DB Stability Check"
echo "========================"

COMPOSE_FILE="infra/docker-compose.yml"

# 1. Проверка подключения
echo -n "1. Database connection: "
if docker compose -f "$COMPOSE_FILE" exec -T db psql -U postgres -d agents -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# 2. Проверка пароля
echo -n "2. Password validation: "
EXPECTED_PASSWORD=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2)
if PGPASSWORD="$EXPECTED_PASSWORD" docker compose -f "$COMPOSE_FILE" exec -T db psql -U postgres -d agents -c "SELECT 1" > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# 3. API health
echo -n "3. API health check: "
if curl -s -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    exit 1
fi

# 4. Проверка логов на ошибки
echo -n "4. No auth errors in logs: "
if docker compose -f "$COMPOSE_FILE" logs api --tail 50 | grep -qi "password authentication failed\|InvalidPasswordError"; then
    echo -e "${RED}✗${NC}"
    echo "   Found authentication errors in logs!"
    docker compose -f "$COMPOSE_FILE" logs api --tail 10 | grep -i "password\|auth"
    exit 1
else
    echo -e "${GREEN}✓${NC}"
fi

# 5. Проверка конфигурации
echo -n "5. No wrapper scripts: "
if grep -q "entrypoint.*wrapper\|db-entrypoint-wrapper" "$COMPOSE_FILE"; then
    echo -e "${RED}✗${NC}"
    exit 1
else
    echo -e "${GREEN}✓${NC}"
fi

echo ""
echo -e "${GREEN}✓ All checks passed!${NC}"
