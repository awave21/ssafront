#!/usr/bin/env bash
# Быстрый деплой сервисов через infra/docker-compose.yml
# Использование:
#   ./scripts/deploy.sh backend
#   ./scripts/deploy.sh frontend
#   ./scripts/deploy.sh worker
#   ./scripts/deploy.sh monitor
#   ./scripts/deploy.sh all
#   ./scripts/deploy.sh full
# Опции:
#   --no-migrate  (для backend/worker/all/full не запускать миграции)

set -euo pipefail

usage() {
  cat <<'EOF'
Использование:
  ./scripts/deploy.sh backend [--no-migrate]
  ./scripts/deploy.sh frontend
  ./scripts/deploy.sh worker [--no-migrate]
  ./scripts/deploy.sh monitor
  ./scripts/deploy.sh all [--no-migrate]
  ./scripts/deploy.sh full [--no-migrate]

Режимы:
  backend   Пересобрать и перезапустить api + sqns-sync-worker (db/redis поднимутся автоматически)
  frontend  Пересобрать и перезапустить frontend
  worker    Пересобрать и перезапустить только sqns-sync-worker
  monitor   Перезапустить мониторинг (netdata + caddy)
  all       Пересобрать и перезапустить api + frontend + sqns-sync-worker + netdata + caddy
  full      Поднять/обновить весь прод-набор (с мониторингом и admin-сервисами)
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

TARGET="$1"
shift || true

if [[ "$TARGET" == "-h" || "$TARGET" == "--help" ]]; then
  usage
  exit 0
fi

RUN_MIGRATIONS=1
for arg in "$@"; do
  case "$arg" in
    --no-migrate) RUN_MIGRATIONS=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Неизвестный аргумент: $arg"; usage; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$INFRA_DIR/.env"
MIGRATIONS_SCRIPT="$SCRIPT_DIR/apply-migrations.sh"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Ошибка: не найден $ENV_FILE"
  echo "Скопируйте шаблон: cp $INFRA_DIR/env.example $ENV_FILE"
  exit 1
fi

if [[ ! -x "$MIGRATIONS_SCRIPT" ]]; then
  echo "Ошибка: не найден исполняемый скрипт миграций $MIGRATIONS_SCRIPT"
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

case "$TARGET" in
  backend)
    echo "Деплой backend: db/redis + пересборка api + sqns-sync-worker"
    "${DC[@]}" up -d db redis
    "${DC[@]}" up -d --build api sqns-sync-worker
    if [[ "$RUN_MIGRATIONS" -eq 1 ]]; then
      "$MIGRATIONS_SCRIPT"
    fi
    ;;
  frontend)
    echo "Деплой frontend: пересборка frontend + проверка sqns-sync-worker"
    "${DC[@]}" up -d --build frontend
    "${DC[@]}" up -d sqns-sync-worker
    ;;
  worker)
    echo "Деплой worker: db/redis + пересборка sqns-sync-worker"
    "${DC[@]}" up -d db redis
    "${DC[@]}" up -d --build sqns-sync-worker
    if [[ "$RUN_MIGRATIONS" -eq 1 ]]; then
      "$MIGRATIONS_SCRIPT"
    fi
    ;;
  monitor)
    echo "Деплой monitor: перезапуск netdata + caddy + проверка sqns-sync-worker"
    "${DC[@]}" up -d netdata caddy
    "${DC[@]}" up -d sqns-sync-worker
    ;;
  all)
    echo "Деплой all: db/redis + пересборка api/frontend/sqns-sync-worker + netdata + caddy"
    "${DC[@]}" up -d db redis
    "${DC[@]}" up -d --build api frontend sqns-sync-worker
    if [[ "$RUN_MIGRATIONS" -eq 1 ]]; then
      "$MIGRATIONS_SCRIPT"
    fi
    "${DC[@]}" up -d --remove-orphans netdata caddy
    ;;
  full)
    echo "Деплой full: db/redis + api/frontend/sqns-sync-worker + netdata/caddy + pgadmin/watcher"
    "${DC[@]}" up -d db redis
    "${DC[@]}" up -d --build api frontend sqns-sync-worker
    if [[ "$RUN_MIGRATIONS" -eq 1 ]]; then
      "$MIGRATIONS_SCRIPT"
    fi
    "${DC[@]}" up -d --remove-orphans netdata caddy pgadmin watcher
    ;;
  *)
    echo "Неизвестный режим: $TARGET"
    usage
    exit 1
    ;;
esac

echo
echo "Готово. Текущий статус:"
"${DC[@]}" ps

MONITOR_PATH_VALUE="$(awk -F= '/^MONITOR_PATH=/{print $2; exit}' "$ENV_FILE" 2>/dev/null || true)"
FRONTEND_SITE_URL_VALUE="$(awk -F= '/^FRONTEND_SITE_URL=/{print $2; exit}' "$ENV_FILE" 2>/dev/null || true)"
MONITOR_AUTH_USER_VALUE="$(awk -F= '/^MONITOR_AUTH_USER=/{print $2; exit}' "$ENV_FILE" 2>/dev/null || true)"

if [[ -n "$MONITOR_PATH_VALUE" && -n "$FRONTEND_SITE_URL_VALUE" ]]; then
  echo
  echo "UI мониторинг: ${FRONTEND_SITE_URL_VALUE%/}${MONITOR_PATH_VALUE}"
  if [[ -n "$MONITOR_AUTH_USER_VALUE" ]]; then
    echo "Пользователь мониторинга: $MONITOR_AUTH_USER_VALUE"
  fi
fi
