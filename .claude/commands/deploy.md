Задеплой последние изменения на продакшн сервер.

## Шаги

1. Проверь незакоммиченные изменения — запусти `git status`. Если есть изменения, сначала выполни /push.

2. Выполни деплой последовательно:

```bash
ssh devuser@5.35.90.66 "cd /opt/myapp/infra && git pull origin main"
```

```bash
ssh devuser@5.35.90.66 "cd /opt/myapp/infra && sudo docker compose exec -T api alembic upgrade head"
```

```bash
ssh devuser@5.35.90.66 "cd /opt/myapp/infra && ./scripts/deploy.sh all"
```

3. Проверь статус:

```bash
ssh devuser@5.35.90.66 "curl -sS https://agentsapp.integration-ai.ru/api/v1/health && sudo docker compose -f /opt/myapp/infra/docker-compose.yml ps"
```

4. Если что-то упало — логи:

```bash
ssh devuser@5.35.90.66 "cd /opt/myapp/infra && sudo docker compose logs --tail=100 api"
```
