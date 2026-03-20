#!/bin/bash

# Скрипт для мониторинга соединений к PostgreSQL

echo "=== PostgreSQL Connection Monitor ==="
echo "Press Ctrl+C to stop"
echo ""

while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Checking connections..."

    # Проверяем количество активных соединений
    ACTIVE_CONNECTIONS=$(psql -h localhost -U postgres -d agents -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "ERROR")

    # Проверяем общее количество соединений
    TOTAL_CONNECTIONS=$(psql -h localhost -U postgres -d agents -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null || echo "ERROR")

    # Проверяем настройку max_connections
    MAX_CONNECTIONS=$(psql -h localhost -U postgres -d agents -t -c "SHOW max_connections;" 2>/dev/null || echo "ERROR")

    echo "Active connections: $ACTIVE_CONNECTIONS"
    echo "Total connections: $TOTAL_CONNECTIONS"
    echo "Max connections: $MAX_CONNECTIONS"
    echo "---"

    # Предупреждение если близко к лимиту
    if [[ "$ACTIVE_CONNECTIONS" =~ ^[0-9]+$ ]] && [[ "$MAX_CONNECTIONS" =~ ^[0-9]+$ ]]; then
        PERCENTAGE=$(( ACTIVE_CONNECTIONS * 100 / MAX_CONNECTIONS ))
        if [ $PERCENTAGE -gt 80 ]; then
            echo "⚠️  WARNING: Connections at ${PERCENTAGE}% of limit!"
        fi
    fi

    echo ""
    sleep 5
done