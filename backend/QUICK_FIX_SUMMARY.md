# ✅ Проблема решена: 500 Error на /api/v1/auth/login

## Что было не так

API не мог подключиться к PostgreSQL из-за неправильного пароля:
```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"
```

## Что было сделано

1. ✅ Сброшен пароль PostgreSQL: `ALTER USER postgres WITH PASSWORD 'postgres';`
2. ✅ Перезапущен API контейнер: `docker compose restart api`
3. ✅ Протестированы все эндпоинты

## Текущий статус

✅ **Все работает:**
- Health endpoint: `http://localhost:8000/api/v1/health` → 200 OK
- Registration: `POST /api/v1/auth/register` → 201 Created
- Login: `POST /api/v1/auth/login` → 200 OK
- Agents: `GET /api/v1/agents` → 200 OK (с JWT токеном)

## Тестовый аккаунт

Для проверки фронтенда используйте:

```
Email: test@example.com
Password: testpass123
```

## Быстрая проверка

```bash
# Тест логина
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}'

# Должен вернуть JWT токен и данные пользователя
```

## Подробная документация

- 📖 [fix-postgres-auth-issue.md](docs/fix-postgres-auth-issue.md) - полное описание решения
- 📖 [database-connection.md](docs/database-connection.md) - инструкция по подключению к БД

---

**Теперь можно тестировать на фронтенде:** https://front.agentsapp.integration-ai.ru
