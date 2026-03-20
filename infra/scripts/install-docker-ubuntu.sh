#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Запустите скрипт от root: sudo bash /opt/myapp/infra/scripts/install-docker-ubuntu.sh"
  exit 1
fi

if command -v docker >/dev/null 2>&1; then
  echo "Docker уже установлен:"
  docker --version
  if docker compose version >/dev/null 2>&1; then
    docker compose version
    echo "Docker Compose plugin уже доступен."
    exit 0
  fi
fi

apt-get update -y
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME}")"
echo \
  "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "Проверка установки:"
docker --version
docker compose version
echo "Установка завершена."
