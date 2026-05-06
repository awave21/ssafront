Задеплой последние изменения на продакшн сервер.

## Шаги

1. Проверь есть ли незакоммиченные изменения (`git status`). Если есть — сначала выполни /push, потом возвращайся к деплою.

2. Выведи пользователю команды для выполнения на сервере:

```bash
cd /opt/myapp/infra
git pull origin main
sudo docker compose exec api alembic upgrade head
./scripts/deploy.sh all
```

3. Если нужен деплой только части:
   - Только бэкенд: `./scripts/deploy.sh backend`
   - Только фронтенд: `./scripts/deploy.sh frontend`
   - Без миграций: `./scripts/deploy.sh backend --no-migrate`

4. После деплоя — проверь что всё работает:

```bash
curl -sS https://agentsapp.integration-ai.ru/api/v1/health
curl -I https://lk.chatmedbot.ru
sudo docker compose ps
```

5. Если что-то упало — посмотри логи:

```bash
sudo docker compose logs --tail=100 api
sudo docker compose logs --tail=100 frontend
```
