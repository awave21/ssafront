#!/bin/sh
# Запуск миграций перед стартом API. Устраняет 500 из-за отсутствующих колонок (max_history_messages, sqns_* и т.д.).
# SKIP_ALEMBIC=1 — не запускать миграции (для восстановления, когда БД недоступна).
set -e

run_alembic() {
  retries=15
  delay=3
  i=0
  while [ $i -lt $retries ]; do
    if alembic -c /app/alembic.ini upgrade head; then
      return 0
    fi
    i=$((i + 1))
    if [ $i -lt $retries ]; then
      echo "entrypoint: alembic failed, retry $i/$retries in ${delay}s"
      sleep $delay
    fi
  done
  return 1
}

if [ "${SKIP_ALEMBIC}" = "1" ]; then
  echo "entrypoint: SKIP_ALEMBIC=1, skipping migrations"
else
  if ! run_alembic; then
    echo "entrypoint: WARNING — alembic upgrade head failed after 15 attempts. Starting API anyway."
    echo "entrypoint: Fix DB and run: ./scripts/fix-db-and-api.sh"
  fi
fi

exec "$@"
