Покажи последние 15 запусков агентов из базы данных.

Подключись через `/opt/myapp/backend/.venv/bin/python` к PostgreSQL:
- host: 172.18.0.4, port: 5432, user: postgres, db: agents
- пароль из `/opt/myapp/infra/.env` (переменная POSTGRES_PASSWORD)

Выполни запрос:
```sql
SELECT
  r.id,
  a.name AS agent_name,
  r.status,
  LEFT(r.input_message, 80) AS input,
  LEFT(r.output_message, 120) AS output,
  r.tools_called,
  r.prompt_tokens,
  r.completion_tokens,
  r.created_at
FROM runs r
JOIN agents a ON a.id = r.agent_id
ORDER BY r.created_at DESC
LIMIT 15;
```

Выведи результат в виде таблицы. Для строк со status != 'completed' выдели их отдельно в секции "Ошибки / незавершённые". Покажи суммарный расход токенов по агентам за сегодня.
