# Подключение к PostgreSQL

## Краткая справка

### 📍 С хост-машины (localhost)
```
Host:     localhost
Port:     5432
User:     postgres
Password: postgres
Database: agents
```

### 🐳 Из Docker контейнеров
```
Host:     db
Port:     5432
User:     postgres
Password: postgres
Database: agents
```

---

## Способы подключения

### 1. pgAdmin (Web UI)

1. Откройте http://localhost:5050
2. Войдите:
   - Email: `moskovets.maksim@yandex.ru`
   - Password: `9hSRYWbNmChIeUkS`
3. Добавьте сервер:
   - Name: `AgentsApp`
   - Host: `db`
   - Port: `5432`
   - Username: `postgres`
   - Password: `postgres`
   - Database: `agents`

### 2. Командная строка (psql)

```bash
# Подключение через Docker
docker compose exec db psql -U postgres -d agents

# Полезные команды
\dt                          # список таблиц
\d agents                    # структура таблицы agents
\x                           # расширенный вывод
SELECT * FROM agents LIMIT 5;
\q                           # выход
```

### 3. GUI клиенты (DBeaver, DataGrip, TablePlus)

Используйте параметры для **localhost** (см. выше).

### 4. Python (asyncpg)

```python
import asyncpg

# С хост-машины
conn = await asyncpg.connect(
    host='localhost',
    port=5432,
    user='postgres',
    password='postgres',
    database='agents'
)

# Из Docker контейнера (используйте переменную окружения)
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/agents
```

---

## Устранение проблем

### Ошибка: "Connection refused"

Проверьте, что контейнеры запущены:
```bash
docker compose ps
```

Если контейнер `db` не запущен:
```bash
docker compose up -d db
```

### Ошибка: "password authentication failed"

Используйте пароль `postgres` (из `.env` файла).

Если ошибка сохраняется, сбросьте пароль:
```bash
docker compose exec db psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
docker compose restart api
```

**См. подробное решение:** [fix-postgres-auth-issue.md](./fix-postgres-auth-issue.md)

### Проверка подключения

```bash
# Проверка порта
nc -zv localhost 5432

# Проверка из контейнера
docker compose exec db psql -U postgres -d agents -c "SELECT version();"
```

---

## Структура базы данных

Текущая база содержит 11 таблиц:
- `agents` - агенты
- `users` - пользователи
- `tenants` - тенанты
- `agent_runs` - запуски агентов
- и другие...

Для просмотра полной структуры используйте pgAdmin или:
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public';
```
