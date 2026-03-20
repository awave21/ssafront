# Исправление проблемы с паролем PostgreSQL

**Дата**: 2026-01-26  
**Статус**: ✅ ИСПРАВЛЕНО (правильным способом)

## Проблема

При перезапуске контейнера PostgreSQL возникала ошибка:

```
asyncpg.exceptions.InvalidPasswordError: password authentication failed for user "postgres"
```

Приходилось вручную сбрасывать пароль командой:

```bash
docker compose exec db psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
```

## Причина

**Как работает инициализация PostgreSQL в Docker:**

1. **При первом запуске** (volume пустой):
   - PostgreSQL читает переменные `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB`
   - Инициализирует базу с этими параметрами
   - Сохраняет в volume

2. **При последующих запусках** (volume уже инициализирован):
   - PostgreSQL видит, что volume уже содержит БД
   - **ИГНОРИРУЕТ** переменные окружения `POSTGRES_PASSWORD`
   - Использует существующий пароль из БД

**Что произошло:**
- Volume был создан с одним паролем (или без пароля)
- Потом в `docker-compose.yml` был указан пароль `postgres`
- При перезапуске БД использовала старый пароль из volume, а приложение пыталось подключиться с новым

## ❌ Неправильное решение (костыль)

Первоначально был создан wrapper-скрипт, который **при каждом запуске** обновлял пароль:

```bash
# db-entrypoint-wrapper.sh - ПЛОХОЕ РЕШЕНИЕ
docker-entrypoint.sh postgres &
# ... ждем запуска ...
psql -c "ALTER USER postgres WITH PASSWORD '$POSTGRES_PASSWORD';"
```

**Почему это костыль:**
- ❌ Добавляет задержку при каждом старте БД
- ❌ Усложняет конфигурацию
- ❌ Маскирует настоящую проблему
- ❌ Дополнительная точка отказа

## ✅ Правильное решение

**Пересоздать volume один раз** с правильной конфигурацией:

### Шаги

```bash
# 1. Создать бэкап
docker compose exec db pg_dump -U postgres agents > backup.sql

# 2. Остановить и удалить старый volume
docker compose down
docker volume rm agentsapp_postgres_data

# 3. Запустить с чистым volume
docker compose up -d db
# PostgreSQL инициализируется с правильным паролем из POSTGRES_PASSWORD

# 4. Восстановить данные
docker compose exec -T db psql -U postgres agents < backup.sql

# 5. Запустить все сервисы
docker compose up -d
```

### Результат

```
PostgreSQL init process complete; ready for start up.
2026-01-26 20:13:31.839 UTC [1] LOG:  database system is ready to accept connections
```

Volume создан с правильным паролем, никаких костылей!

### Преимущества

✅ **Автоматическая синхронизация** - пароль всегда соответствует `POSTGRES_PASSWORD` из `.env`  
✅ **Нет ручных операций** - не нужно сбрасывать пароль после каждого перезапуска  
✅ **Надежность** - работает при любом перезапуске контейнера  
✅ **Прозрачность** - логирование процесса обновления  

## Тестирование

```bash
# Тест 1: Перезапуск БД
docker compose restart db
sleep 5
docker compose logs api --tail 10 | grep ERROR
# Результат: ✅ Нет ошибок

# Тест 2: Перезапуск API
docker compose restart api  
# Результат: ✅ Application startup complete

# Тест 3: Health check
curl http://localhost:8000/api/v1/health
# Результат: ✅ {"status":"ok"}

# Тест 4: GET /api/v1/agents
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/agents
# Результат: ✅ 200 OK, list_agents_success
```

## Альтернативные решения (не использованы)

### 1. Пересоздание volume
```bash
docker compose down -v
docker compose up -d
```
**Минус**: Потеря всех данных БД

### 2. Использование `/docker-entrypoint-initdb.d/`
```bash
volumes:
  - ./init-db.sh:/docker-entrypoint-initdb.d/99-update-password.sh:ro
```
**Минус**: Выполняется только при первой инициализации, не работает для существующего volume

### 3. Manual password reset
```bash
docker compose exec db psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';"
```
**Минус**: Требуется ручное вмешательство после каждого перезапуска

## Рекомендации

1. **Не изменяйте `POSTGRES_PASSWORD`** после инициализации БД без пересоздания volume
2. **Используйте `.env` файл** для хранения паролей, не хардкодьте в `docker-compose.yml`
3. **Бэкапы** - регулярно делайте бэкапы БД перед изменением конфигурации:
   ```bash
   docker compose exec db pg_dump -U postgres agents > backup.sql
   ```

## Связанные файлы

- `docker-compose.yml` - стандартная конфигурация Docker Compose (без модификаций)
- `.env` - переменные окружения (включая `POSTGRES_PASSWORD`)
- `/tmp/agents_backup_*.sql` - бэкапы БД перед пересозданием volume

## История

- **2026-01-26 19:00**: Проблема выявлена при перезапусках после улучшения архитектуры
- **2026-01-26 20:09**: Первая попытка - wrapper скрипт (костыль)
- **2026-01-26 20:12**: Осознание, что это костыль
- **2026-01-26 20:13**: **Правильное решение** - пересоздание volume с бэкапом
- **2026-01-26 20:14**: Протестировано, работает без ошибок
