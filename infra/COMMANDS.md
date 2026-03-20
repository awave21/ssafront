# Команды деплоя и обслуживания

Все команды выполнять из `infra`:

```bash
cd /opt/myapp/infra
```

Для удобства:

```bash
DC="sudo docker compose"
```

## Быстрый деплой (одной командой)

```bash
# Backend (api + sqns-sync-worker + авто-миграции)
./scripts/deploy.sh backend

# Frontend
./scripts/deploy.sh frontend

# Только SQNS worker
./scripts/deploy.sh worker

# Полный деплой (api + frontend + sqns-sync-worker + caddy + авто-миграции)
./scripts/deploy.sh all

# Если нужно без миграций
./scripts/deploy.sh backend --no-migrate
./scripts/deploy.sh worker --no-migrate
./scripts/deploy.sh all --no-migrate
```

## Быстрый статус

```bash
$DC ps
$DC logs --tail=120 api frontend caddy
```

## Полный запуск/перезапуск стека

```bash
# Поднять все сервисы (если еще не подняты)
$DC up -d

# Полная пересборка всех образов + перезапуск
$DC up -d --build

# Применить миграции (рекомендуемый способ)
./scripts/apply-migrations.sh
```

## Частичная пересборка

```bash
# Пересобрать и перезапустить только backend (api)
$DC up -d --build api
./scripts/apply-migrations.sh
$DC logs --tail=120 api

# Пересобрать и перезапустить только frontend
$DC up -d --build frontend
$DC logs --tail=120 frontend
```

## Перезапуск без пересборки

```bash
# Перезапустить сервисы
$DC restart api
$DC restart frontend
$DC restart caddy

# Если меняли только .env для caddy (например DOCS_AUTH_*):
$DC up -d --force-recreate caddy
```

## Caddy (валидация и применение конфига)

```bash
# Проверить синтаксис Caddyfile
$DC exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile

# Перечитать конфиг без полного рестарта контейнера
$DC exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

## Проверки доменов

```bash
# API health (GET, не HEAD)
curl -sS https://api.chatmedbot.ru/api/v1/health

# Фронт
curl -I https://lk.chatmedbot.ru

# Документация должна быть защищена
curl -I https://api.chatmedbot.ru/docs
curl -I https://api.chatmedbot.ru/openapi.json

# Проверка с авторизацией docs
curl -u docs_admin:YOUR_PASSWORD -I https://api.chatmedbot.ru/docs
```

## Логи и диагностика

```bash
# Логи по сервисам
$DC logs --tail=200 api
$DC logs --tail=200 frontend
$DC logs --tail=200 caddy
$DC logs --tail=200 db

# Смотреть логи в реальном времени
$DC logs -f api caddy frontend
```

## Миграции (отдельно)

```bash
# Рекомендуемый единый скрипт из infra
./scripts/apply-migrations.sh

# Эквивалент вручную:
$DC up -d db redis
$DC exec -T api alembic -c /app/alembic.ini upgrade head

# Совместимость со старым путем (проксирует в infra):
/opt/myapp/backend/scripts/apply-migrations.sh
```

## База данных: бэкап и восстановление

```bash
# Бэкап базы agents в custom dump
$DC exec -T db pg_dump -U postgres -d agents -Fc > /opt/myapp/backend/backups_back/postgres_$(date +%F_%H-%M-%S).dump

# Бэкап глобальных объектов (роли)
$DC exec -T db pg_dumpall -U postgres --globals-only > /opt/myapp/backend/backups_back/postgres_globals_$(date +%F_%H-%M-%S).sql

# Восстановить globals
$DC exec -T db psql -U postgres -d postgres < /opt/myapp/backend/backups_back/postgres_globals_YYYY-MM-DD_HH-MM-SS.sql

# Восстановить БД из dump
$DC exec -T db pg_restore -v --clean --if-exists --no-owner --no-privileges -U postgres -d agents < /opt/myapp/backend/backups_back/postgres_YYYY-MM-DD_HH-MM-SS.dump
```

## Остановка

```bash
# Остановить и удалить контейнеры/сеть (данные в volumes останутся)
$DC down

# Полный сброс с удалением volumes (ОПАСНО: удалит данные БД)
$DC down -v
```

