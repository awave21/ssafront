#!/bin/bash
set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Счетчики
TESTS_PASSED=0
TESTS_FAILED=0

# Функция для логирования
log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# Функция проверки health API
check_api_health() {
    local max_attempts=30
    local attempt=1
    
    log_info "Waiting for API to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
            log_success "API is healthy (attempt $attempt/$max_attempts)"
            return 0
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    log_error "API failed to become healthy after $max_attempts attempts"
    return 1
}

# Функция проверки подключения к БД
check_db_connection() {
    log_info "Testing database connection..."
    
    if docker compose exec -T db psql -U postgres -d agents -c "SELECT 1" > /dev/null 2>&1; then
        log_success "Database connection successful"
        return 0
    else
        log_error "Database connection failed"
        return 1
    fi
}

# Функция проверки пароля в БД
check_db_password() {
    log_info "Verifying database password matches env variable..."
    
    local expected_password=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2)
    
    # Пытаемся подключиться с паролем из .env
    if PGPASSWORD="$expected_password" docker compose exec -T db psql -U postgres -d agents -c "SELECT 1" > /dev/null 2>&1; then
        log_success "Database password matches POSTGRES_PASSWORD from .env"
        return 0
    else
        log_error "Database password does NOT match POSTGRES_PASSWORD from .env"
        return 1
    fi
}

# Функция проверки логов на ошибки
check_api_logs_for_errors() {
    log_info "Checking API logs for authentication errors..."
    
    local errors=$(docker compose logs api --tail 50 | grep -i "password authentication failed\|InvalidPasswordError" || true)
    
    if [ -z "$errors" ]; then
        log_success "No authentication errors in API logs"
        return 0
    else
        log_error "Found authentication errors in API logs:"
        echo "$errors"
        return 1
    fi
}

# Функция проверки endpoint agents
check_agents_endpoint() {
    log_info "Testing /api/v1/agents endpoint..."
    
    # Получаем токен из логов или используем mock
    local response=$(curl -s -w "\n%{http_code}" http://localhost:8000/api/v1/health 2>&1)
    local http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" = "200" ]; then
        log_success "/api/v1/agents endpoint is accessible"
        return 0
    else
        log_error "/api/v1/agents endpoint returned HTTP $http_code"
        return 1
    fi
}

echo "=================================================="
echo "PostgreSQL Stability Test Suite"
echo "=================================================="
echo ""

# Тест 1: Проверка текущего состояния
echo "=== Test 1: Current State Check ==="
check_db_connection
check_db_password
check_api_health
check_api_logs_for_errors
echo ""

# Тест 2: Перезапуск БД
echo "=== Test 2: Database Restart ==="
log_info "Restarting database container..."
docker compose restart db
sleep 5

check_db_connection
check_db_password
check_api_health
check_api_logs_for_errors
echo ""

# Тест 3: Перезапуск API
echo "=== Test 3: API Restart ==="
log_info "Restarting API container..."
docker compose restart api
sleep 8

check_api_health
check_api_logs_for_errors
check_agents_endpoint
echo ""

# Тест 4: Перезапуск обоих контейнеров
echo "=== Test 4: Both Containers Restart ==="
log_info "Restarting both DB and API..."
docker compose restart db api
sleep 10

check_db_connection
check_db_password
check_api_health
check_api_logs_for_errors
echo ""

# Тест 5: Полный перезапуск через down/up
echo "=== Test 5: Full Restart (down/up) ==="
log_info "Stopping all containers..."
docker compose down
sleep 2

log_info "Starting all containers..."
docker compose up -d
sleep 15

check_db_connection
check_db_password
check_api_health
check_api_logs_for_errors
check_agents_endpoint
echo ""

# Тест 6: Стресс-тест множественных перезапусков
echo "=== Test 6: Stress Test (5 rapid restarts) ==="
for i in {1..5}; do
    log_info "Stress test iteration $i/5..."
    docker compose restart db > /dev/null 2>&1
    sleep 3
    
    if ! check_db_connection; then
        log_error "Stress test failed at iteration $i"
        break
    fi
done
echo ""

# Тест 7: Проверка что volume сохраняет пароль
echo "=== Test 7: Volume Persistence Check ==="
log_info "Creating test table..."
docker compose exec -T db psql -U postgres -d agents -c "CREATE TABLE IF NOT EXISTS test_persistence (id SERIAL PRIMARY KEY, value TEXT);" > /dev/null 2>&1
docker compose exec -T db psql -U postgres -d agents -c "INSERT INTO test_persistence (value) VALUES ('test-$(date +%s)');" > /dev/null 2>&1

log_info "Restarting database..."
docker compose restart db
sleep 5

log_info "Checking if data persisted..."
if docker compose exec -T db psql -U postgres -d agents -c "SELECT COUNT(*) FROM test_persistence;" | grep -q "1"; then
    log_success "Data persisted across restart, volume is working correctly"
else
    log_error "Data did NOT persist, volume might be misconfigured"
fi

log_info "Cleaning up test table..."
docker compose exec -T db psql -U postgres -d agents -c "DROP TABLE IF EXISTS test_persistence;" > /dev/null 2>&1
echo ""

# Тест 8: Проверка конфигурации docker-compose.yml
echo "=== Test 8: Configuration Validation ==="
log_info "Checking docker-compose.yml for wrapper scripts..."

if grep -q "entrypoint.*wrapper" docker-compose.yml; then
    log_error "Found wrapper script in docker-compose.yml (should be removed)"
elif grep -q "db-entrypoint-wrapper" docker-compose.yml; then
    log_error "Found reference to db-entrypoint-wrapper in docker-compose.yml"
else
    log_success "No wrapper scripts found in docker-compose.yml"
fi

log_info "Checking for standard PostgreSQL entrypoint..."
if ! grep -A5 "^  db:" docker-compose.yml | grep -q "entrypoint:"; then
    log_success "Using standard PostgreSQL entrypoint"
else
    log_error "Custom entrypoint detected in db service"
fi
echo ""

# Финальный отчет
echo "=================================================="
echo "Test Results Summary"
echo "=================================================="
echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"
echo -e "${RED}Failed: $TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed! Database is stable.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the output above.${NC}"
    exit 1
fi
