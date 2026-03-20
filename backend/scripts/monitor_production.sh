#!/bin/bash

# Быстрый мониторинг production развертывания

echo "🔍 Production мониторинг: https://agentsapp.integration-ai.ru"
echo "Обновление каждые 30 секунд... (Ctrl+C для выхода)"
echo

while true; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Проверка состояния..."

    # Проверяем API
    HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://agentsapp.integration-ai.ru/health 2>/dev/null || echo "ERROR")

    if [ "$HEALTH_STATUS" = "200" ]; then
        echo "✅ API Health: OK"

        # Получаем информацию о БД
        DB_INFO=$(curl -s https://agentsapp.integration-ai.ru/health/db 2>/dev/null || echo "{}")

        if echo "$DB_INFO" | jq -e '.database' >/dev/null 2>&1; then
            ACTIVE=$(echo "$DB_INFO" | jq -r '.database.active_connections // "N/A"')
            TOTAL=$(echo "$DB_INFO" | jq -r '.database.total_connections // "N/A"')
            USAGE=$(echo "$DB_INFO" | jq -r '.database.usage_percent // "N/A"')
            MAX=$(echo "$DB_INFO" | jq -r '.database.max_connections // "N/A"')

            echo "📊 БД Соединения:"
            echo "   Активных: $ACTIVE"
            echo "   Всего: $TOTAL"
            echo "   Использование: $USAGE%"
            echo "   Максимум: $MAX"

            # Предупреждения
            if [[ "$USAGE" =~ ^[0-9]+(\.[0-9]+)?$ ]] && (( $(echo "$USAGE > 80" | bc -l) )); then
                echo "⚠️  ВНИМАНИЕ: Высокая загрузка соединений!"
            fi
        else
            echo "❌ Не удалось получить информацию о БД"
        fi
    else
        echo "❌ API Health: FAILED (HTTP $HEALTH_STATUS)"
    fi

    echo "---"
    sleep 30
done