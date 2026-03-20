#!/usr/bin/env bash
# Обертка для обратной совместимости.
# Основной скрипт миграций находится в infra/scripts/apply-migrations.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
INFRA_SCRIPT="$ROOT_DIR/infra/scripts/apply-migrations.sh"

if [[ ! -x "$INFRA_SCRIPT" ]]; then
  echo "Ошибка: не найден исполняемый скрипт $INFRA_SCRIPT"
  echo "Запустите миграции вручную:"
  echo "  cd $ROOT_DIR/infra && sudo docker compose exec api alembic -c /app/alembic.ini upgrade head"
  exit 1
fi

echo "Переадресация миграций в infra/scripts/apply-migrations.sh"
exec "$INFRA_SCRIPT"
