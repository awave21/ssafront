Задеплой последние изменения на продакшн сервер.

## Шаги

1. Проверь незакоммиченные изменения — запусти `git status`. Если есть изменения, сначала выполни /push.

2. Запусти скрипт деплоя:

```bash
cd /Users/maksimmoskovec/Documents/ИИ\ агенты/Агентская\ система/ssafront/infra && ./scripts/deploy.sh all
```

3. Выведи результат выполнения скрипта пользователю.

4. Если скрипт завершился с ошибкой — покажи логи:

```bash
cd /Users/maksimmoskovec/Documents/ИИ\ агенты/Агентская\ система/ssafront/infra && sudo docker compose logs --tail=100 api
```
