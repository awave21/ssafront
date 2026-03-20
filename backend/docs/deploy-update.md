# Обновление изменений на сервере

> **Почему снова 500 на `/api/v1/agents`?** — см. [docs/root-cause-500-agents.md](root-cause-500-agents.md): пароль БД в томе vs `DATABASE_URL` и неприменённые миграции.

> **«Не работает» — с чего начать:** `./scripts/diagnose-api.sh` — выведет статус контейнеров, логи API, ответы /health и /health/db и подскажет, что делать.

## 1. Подтянуть код

**Через Git (если репозиторий на сервере):**
```bash
cd /root/agentsapp
git pull
```

**Вручную (rsync/scp):** скопировать изменённые файлы:
- `backend/app/`, `backend/alembic/`, `backend/alembic.ini`, `backend/entrypoint.sh`
- `scripts/fix-db-and-api.sh`, `scripts/link_sqns_token_to_agent.py`

---

## 2. Перезапустить API

В `docker-compose` каталог `./backend` смонтирован в контейнер как `/app`, поэтому новый код уже виден внутри. Достаточно перезапустить процесс:

```bash
cd /root/agentsapp
docker compose restart api
```

Или по имени контейнера:
```bash
docker restart agentsapp-api-1
```

Пересборка образа (`docker compose build api`) нужна **один раз**, если добавлен `entrypoint.sh` (автозапуск миграций при старте API). Дальше при правках только в `./backend` достаточно `restart api` — код подхватывается из volume.

---

## 3. При необходимости: БД и пароль

Если после обновления снова 500 на `/api/v1/agents` из‑за БД:

```bash
./scripts/fix-db-and-api.sh
```

Скрипт сбрасывает пароль `postgres`, прогоняет миграции и перезапускает API.

---

## 4. Если 502 Bad Gateway

502 обычно значит: **прокси (nginx) не получил ответ от API** — контейнер API падает, в рестарт-лупе или не стартует.

**Проверить:**
```bash
docker compose ps api    # статус: Up или Restarting
docker compose logs api --tail 80
```

**Раньше:** при неудаче `alembic upgrade head` (пароль БД, колонки и т.п.) entrypoint делал `exit 1` → контейнер падал → 502.  
**Сейчас:** при неудаче миграций entrypoint **не выходит**, пишет предупреждение и запускает gunicorn. Контейнер остаётся Up; `/api/v1/agents` может отдавать **500** — тогда запустите `./scripts/fix-db-and-api.sh`.

**Если API всё равно не поднимается:** временно отключить миграции: в `docker-compose.yml` у сервиса `api` в `environment` добавить `SKIP_ALEMBIC: "1"`, затем `docker compose up -d api`. После починки БД — убрать переменную и перезапустить.

---

## 5. При необходимости: привязка SQNS-токена к агенту

```bash
PYTHONPATH=./backend \
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/agents \
python scripts/link_sqns_token_to_agent.py \
  --agent-id <UUID> \
  --token "<JWT>" \
  --host "https://your-sqns-host.example.com"
```

`DATABASE_URL` — с `localhost:5432`, если порт БД проброшен на хост.

---

## Краткая последовательность (обычное обновление)

```bash
cd /root/agentsapp
git pull
docker compose restart api
```
