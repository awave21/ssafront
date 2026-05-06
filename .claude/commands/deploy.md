Задеплой последние изменения на продакшн сервер.

## Шаги

1. Проверь незакоммиченные изменения — запусти `git status`. Если есть изменения, сначала выполни /push.

2. Выведи пользователю следующий блок команд для выполнения на сервере 5.35.90.66:

```bash
cd /opt/myapp/infra
git pull origin main
sudo docker compose exec -T api alembic upgrade head
./scripts/deploy.sh all
```

3. После того как пользователь сообщит что деплой завершён, выведи команды проверки:

```bash
curl -sS https://agentsapp.integration-ai.ru/api/v1/health
sudo docker compose ps
```

4. Если что-то упало — команды для логов:

```bash
sudo docker compose logs --tail=100 api
sudo docker compose logs --tail=100 frontend
```
