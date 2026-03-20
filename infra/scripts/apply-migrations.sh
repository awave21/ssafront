#!/usr/bin/env bash
# Применение миграций Alembic через infra/docker-compose.yml
# Использование: ./scripts/apply-migrations.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$INFRA_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Ошибка: не найден $ENV_FILE"
  echo "Скопируйте шаблон: cp $INFRA_DIR/env.example $ENV_FILE"
  exit 1
fi

cd "$INFRA_DIR"

if docker info >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif sudo docker info >/dev/null 2>&1 && sudo docker compose version >/dev/null 2>&1; then
  DC=(sudo docker compose)
elif docker info >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
  DC=(docker-compose)
elif sudo docker info >/dev/null 2>&1 && sudo docker-compose version >/dev/null 2>&1; then
  DC=(sudo docker-compose)
else
  echo "Ошибка: docker/docker compose недоступны."
  echo "Проверьте установку Docker и права пользователя (группа docker или sudo)."
  exit 1
fi

echo "Поднимаю зависимости (db, redis)..."
"${DC[@]}" up -d db redis

POSTGRES_USER_VALUE="${POSTGRES_USER:-postgres}"
POSTGRES_DB_VALUE="${POSTGRES_DB:-postgres}"

echo "Жду готовности PostgreSQL..."
for i in $(seq 1 30); do
  if "${DC[@]}" exec -T db pg_isready -U "$POSTGRES_USER_VALUE" -d "$POSTGRES_DB_VALUE" >/dev/null 2>&1; then
    break
  fi
  if [[ "$i" -eq 30 ]]; then
    echo "Ошибка: PostgreSQL не стал ready за отведенное время."
    exit 1
  fi
  sleep 2
done

API_RUNNING="$("${DC[@]}" ps -q api 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$API_RUNNING" == "0" ]]; then
  echo "API контейнер не запущен, запускаю одноразовый контейнер для миграций..."
  "${DC[@]}" run --rm api alembic -c /app/alembic.ini upgrade head
else
  echo "API контейнер запущен, применяю миграции через exec..."
  "${DC[@]}" exec -T api alembic -c /app/alembic.ini upgrade head
fi

echo "Миграции успешно применены."
