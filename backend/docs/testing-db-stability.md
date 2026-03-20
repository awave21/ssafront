# Тестирование стабильности базы данных

**Дата**: 2026-01-26  
**Цель**: Убедиться, что проблема с паролем PostgreSQL больше не возникнет

## Скрипты тестирования

### 1. Быстрая проверка (30 секунд)

```bash
./test-db-stability-quick.sh
```

**Что проверяет:**
- ✅ Подключение к БД работает
- ✅ Пароль соответствует переменной окружения
- ✅ API отвечает на health endpoint
- ✅ Нет ошибок аутентификации в логах
- ✅ Нет wrapper-скриптов в конфигурации

**Когда использовать:**
- После изменений в `docker-compose.yml`
- После обновления `.env`
- Перед коммитом изменений
- Ежедневно для проверки стабильности

### 2. Полное тестирование (5-10 минут)

```bash
./test-db-stability.sh
```

**Что проверяет:**

#### Test 1: Current State Check
- Текущее состояние БД и API
- Базовая проверка работоспособности

#### Test 2: Database Restart
- Перезапуск контейнера БД
- Проверка что пароль сохранился
- Проверка что API переподключился

#### Test 3: API Restart
- Перезапуск контейнера API
- Проверка что подключение восстановлено
- Проверка endpoints

#### Test 4: Both Containers Restart
- Одновременный перезапуск БД и API
- Проверка синхронизации

#### Test 5: Full Restart (down/up)
- Полная остановка всех контейнеров
- Запуск с нуля
- Проверка что volume сохранил данные

#### Test 6: Stress Test
- 5 быстрых последовательных перезапусков БД
- Проверка стабильности под нагрузкой

#### Test 7: Volume Persistence
- Создание тестовых данных
- Перезапуск БД
- Проверка что данные сохранились

#### Test 8: Configuration Validation
- Проверка что нет wrapper-скриптов
- Проверка стандартного entrypoint
- Валидация конфигурации

**Когда использовать:**
- После решения проблем с БД
- Перед релизом в продакшн
- После миграций
- Еженедельно для профилактики

## Автоматизация через GitHub Actions

Создан workflow `.github/workflows/db-stability-test.yml`, который:

- ✅ Запускается при push в `main` или `develop`
- ✅ Запускается при изменении `docker-compose.yml`, `.env`, `backend/**`
- ✅ Запускается ежедневно в 3:00 UTC
- ✅ Можно запустить вручную (workflow_dispatch)

**Что делает:**
1. Запускает все сервисы
2. Ждет готовности API
3. Выполняет быструю проверку
4. Тестирует перезапуск БД
5. Тестирует перезапуск API
6. Тестирует полный перезапуск
7. Собирает логи при ошибках

## Ручное тестирование

### Сценарий 1: Проверка после изменений

```bash
# 1. Внести изменения в docker-compose.yml или .env
vim docker-compose.yml

# 2. Применить изменения
docker compose up -d

# 3. Быстрая проверка
./test-db-stability-quick.sh

# 4. Если быстрая проверка прошла, запустить полное тестирование
./test-db-stability.sh
```

### Сценарий 2: Проверка существующей системы

```bash
# Запустить быструю проверку
./test-db-stability-quick.sh

# Если есть проблемы, посмотреть логи
docker compose logs db --tail 50
docker compose logs api --tail 50

# Проверить пароль вручную
docker compose exec db psql -U postgres -d agents -c "SELECT 1"
```

### Сценарий 3: Имитация сбоя

```bash
# 1. Остановить БД
docker compose stop db

# 2. Подождать 10 секунд
sleep 10

# 3. Запустить БД
docker compose start db

# 4. Проверить восстановление
./test-db-stability-quick.sh
```

### Сценарий 4: Проверка после перезагрузки хоста

```bash
# 1. Перезагрузить сервер
sudo reboot

# 2. После загрузки, запустить сервисы
cd /root/agentsapp
docker compose up -d

# 3. Подождать готовности
sleep 15

# 4. Проверить стабильность
./test-db-stability-quick.sh
```

## Что делать если тесты падают

### Ошибка: "Database connection failed"

**Причина:** БД не запустилась или недоступна

**Решение:**
```bash
# Проверить статус
docker compose ps db

# Проверить логи
docker compose logs db --tail 50

# Перезапустить
docker compose restart db
```

### Ошибка: "Database password does NOT match"

**Причина:** Пароль в volume не соответствует переменной окружения

**Решение:**
```bash
# КРИТИЧНО: Сделать бэкап
docker compose exec db pg_dump -U postgres agents > backup.sql

# Пересоздать volume
docker compose down
docker volume rm agentsapp_postgres_data
docker compose up -d db

# Восстановить данные
docker compose exec -T db psql -U postgres agents < backup.sql
```

### Ошибка: "API failed to become healthy"

**Причина:** API не может подключиться к БД

**Решение:**
```bash
# Проверить логи API
docker compose logs api --tail 50

# Проверить переменные окружения
docker compose exec api env | grep POSTGRES

# Проверить что БД работает
docker compose exec db psql -U postgres -c "SELECT 1"

# Перезапустить API
docker compose restart api
```

### Ошибка: "Found wrapper script in docker-compose.yml"

**Причина:** Остались старые костыли

**Решение:**
```bash
# Удалить wrapper script из docker-compose.yml
vim docker-compose.yml
# Убрать строки с entrypoint и db-entrypoint-wrapper.sh

# Удалить файл скрипта
rm -f db-entrypoint-wrapper.sh

# Применить изменения
docker compose up -d db
```

## Мониторинг в продакшн

### Prometheus метрики

Добавить проверку здоровья БД:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'postgres'
    static_configs:
      - targets: ['db:5432']
```

### Alerting

Настроить алерты для:
- Недоступность БД > 30 секунд
- Ошибки аутентификации > 3 за 5 минут
- Перезапуск контейнера БД
- Высокое количество соединений

### Healthcheck в docker-compose.yml

```yaml
db:
  image: postgres:16
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres -d agents"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 10s
```

## Расписание проверок

- **Ежедневно**: Быстрая проверка через cron
- **Еженедельно**: Полное тестирование
- **После изменений**: Оба теста
- **Перед релизом**: Полное тестирование + ручная проверка

## Checklist перед продакшн

- [ ] Быстрая проверка прошла успешно
- [ ] Полное тестирование прошло успешно
- [ ] Нет wrapper-скриптов в конфигурации
- [ ] `.env` содержит правильный пароль
- [ ] Бэкап БД создан
- [ ] Volume инициализирован с правильным паролем
- [ ] GitHub Actions workflow настроен
- [ ] Мониторинг настроен
- [ ] Документация обновлена

## Заключение

С этими тестами вы можете быть уверены, что:

✅ Пароль БД всегда соответствует переменной окружения  
✅ Перезапуски контейнеров не вызывают проблем  
✅ Volume корректно сохраняет данные  
✅ Нет костылей в конфигурации  
✅ Проблемы обнаруживаются автоматически  

**Запускайте тесты регулярно!** 🚀
