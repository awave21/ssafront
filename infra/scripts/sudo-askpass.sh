#!/usr/bin/env bash
# Askpass-хелпер для `sudo -A`, используется scripts/deploy.sh.
#
# Отдаёт на stdout пароль sudo, взятый из infra/.env (ключ DEPLOY_SUDO_PASSWORD).
# Сам пароль здесь НЕ хранится: .env лежит вне git и держится в правах 600.
# Если ключа нет или он пуст — выходим с ошибкой, и sudo спросит пароль обычным путём.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

[[ -f "$ENV_FILE" ]] || exit 1

# cut -d= -f2- — пароль может содержать «=»; срезаем только первый разделитель.
pass="$(grep -m1 -E '^DEPLOY_SUDO_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"

# Снимаем обрамляющие кавычки, если значение записано как "..." или '...'.
pass="${pass%\"}"; pass="${pass#\"}"
pass="${pass%\'}"; pass="${pass#\'}"

[[ -n "$pass" ]] || exit 1
printf '%s\n' "$pass"
