# Agent Platform API (Backend)

Полнофункциональная платформа для создания, управления и запуска AI-агентов с поддержкой инструментов (tools) и tool-calling.

## Возможности платформы

### 🎯 Основные функции
- **Управление агентами**: Создание, настройка и публикация AI-агентов с различными моделями и параметрами
- **Регистрация инструментов**: Поддержка HTTP webhook и внутренних инструментов с различными типами аутентификации
- **Привязка инструментов**: Гибкая система привязки инструментов к агентам с настройками разрешений и безопасности
- **Запуск агентов**: Синхронное и асинхронное выполнение агентов с поддержкой streaming через SSE
- **Аутентификация**: JWT-токены и API-ключи с системой ролей и разрешений
- **Аудит**: Полное логирование всех действий пользователей
- **Rate limiting**: Защита от перегрузки с настраиваемыми лимитами
- **Многоарендность**: Полная изоляция данных между арендаторами (tenants)

### 🏗️ Архитектура

#### Модели данных
- **Agent**: AI-агент с системным промптом, моделью и параметрами LLM
- **Tool**: Инструмент с JSON-схемой входных параметров, endpoint'ом и настройками аутентификации
- **Binding**: Привязка инструмента к агенту с настройками разрешений и безопасности
- **Run**: Запуск агента с входным сообщением и результатом выполнения
- **ApiKey**: API-ключи для аутентификации пользователей

#### Службы
- **Runtime Service**: Выполнение агентов с использованием PydanticAI
- **Tool Executor**: HTTP-клиент для вызова инструментов с повторными попытками и валидацией
- **Audit Service**: Логирование всех действий для аудита
- **Secrets Service**: Управление секретами для аутентификации инструментов

## API Reference

### Аутентификация (`/auth`)

#### `POST /auth/token`
Получение JWT-токена по API-ключу.

**Запрос:**
```http
POST /auth/token
Content-Type: application/json
x-api-key: your-api-key

{
  "api_key": "your-api-key"  // альтернативно через заголовок
}
```

**Ответ:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### `GET /auth/test-token`
Получение тестового токена (только в dev окружении).

### API-ключи (`/api-keys`)

#### `POST /api-keys`
Создание нового API-ключа.

**Тело запроса:**
```json
{
  "scopes": ["tools:read", "tools:write"]
}
```

#### `GET /api-keys`
Получение списка API-ключей пользователя.

**Параметры:**
- `include_revoked` (boolean): Включать отозванные ключи

#### `DELETE /api-keys/{api_key_id}`
Отзыв API-ключа.

### Учетные данные (`/credentials`)

#### `POST /credentials`
Создание новой записи учетных данных для инструментов.

**Тело запроса:**
```json
{
  "name": "weather_service",
  "auth_type": "api_key",
  "config": {
    "header": "x-api-key",
    "value": "secret-weather-key"
  },
  "is_active": true
}
```

#### `GET /credentials`
Получение списка учетных данных. По умолчанию возвращаются только активные записи.

**Параметры:**
- `include_inactive` (boolean): возвращать также отключенные.

#### `GET /credentials/{credential_id}`
Подробности по конкретной записи учетных данных.

#### `PUT /credentials/{credential_id}`
Обновление имени, состояния или конфигурации учетных данных. `config` шифруется при сохранении.

#### `DELETE /credentials/{credential_id}`
Деактивация записи (soft delete). Переходится `is_active=false`.

#### `POST /credentials/{credential_id}/test`
Тест вызова эндпоинта с указанным типом аутентификации.

**Тело запроса:**
```json
{
  "method": "POST",
  "endpoint": "https://api.weather.com/health",
  "json": { "city": "Moscow" },
  "timeout_seconds": 5,
  "allowed_domains": ["api.weather.com"]
}
```

**Ответ:**
```json
{
  "status_code": 200,
  "body": "..."
}
```

### Агенты (`/agents`)

#### `POST /agents`
Создание нового агента.

**Тело запроса:**
```json
{
  "name": "MyAgent",
  "system_prompt": "You are a helpful assistant.",
  "model": "openai:gpt-4.1-mini",
  "llm_params": {
    "temperature": 0.7,
    "max_tokens": 1000
  },
  "status": "draft",
  "version": 1
}
```

**Доступные модели:**
- `openai:gpt-4.1` - флагманская модель с улучшенным кодированием
- `openai:gpt-4.1-mini` - быстрая и экономичная модель
- `openai:gpt-4.1-nano` - нано-модель для низкой задержки
- `openai:gpt-4o` - предыдущая версия
- `openai:gpt-4o-mini` - предыдущая мини-версия
- `openai:gpt-5.2` - новейшая модель (если доступна)

#### `GET /agents`
Получение списка агентов.

**Параметры:**
- `limit` (int): Максимальное количество (по умолчанию 50)
- `offset` (int): Смещение (по умолчанию 0)

#### `GET /agents/{agent_id}`
Получение агента по ID.

#### `PUT /agents/{agent_id}`
Обновление агента.

#### `POST /agents/{agent_id}/publish`
Публикация агента (увеличение версии).

#### `DELETE /agents/{agent_id}`
Удаление агента (мягкое удаление).

### Инструменты (`/tools`)

#### `POST /tools`
Создание нового инструмента.

**Тело запроса:**
```json
{
  "name": "weather_api",
  "description": "Get current weather information",
  "input_schema": {
    "type": "object",
    "properties": {
      "city": {
        "type": "string",
        "description": "City name"
      },
      "country": {
        "type": "string",
        "description": "Country code"
      }
    },
    "required": ["city"]
  },
  "execution_type": "http_webhook",
  "endpoint": "https://api.weather.com/v1/current",
  "auth_type": "api_key",
  "status": "active",
  "version": 1
}
```

#### `GET /tools`
Получение списка инструментов.

#### `GET /tools/{tool_id}`
Получение инструмента по ID.

#### `PUT /tools/{tool_id}`
Обновление инструмента.

#### `DELETE /tools/{tool_id}`
Удаление инструмента.

### Привязки (`/agents/{agent_id}/tools`)

#### `POST /agents/{agent_id}/tools/{tool_id}`
Привязка инструмента к агенту.

**Тело запроса:**
```json
{
  "permission_scope": "read",
  "timeout_ms": 15000,
  "rate_limit": "10/minute",
  "allowed_domains": ["api.weather.com", "weather-api.com"],
  "secrets_ref": "WEATHER_API_KEY"
}
```

#### `GET /agents/{agent_id}/tools`
Получение списка привязанных инструментов.

#### `DELETE /agents/{agent_id}/tools/{tool_id}`
Удаление привязки инструмента.

### Запуски (`/runs`)

#### `POST /runs`
Синхронный запуск агента.

**Тело запроса:**
```json
{
  "agent_id": "uuid",
  "input_message": "Hello, please use the weather tool to get current weather in Moscow",
  "session_id": "optional-session-uuid"
}
```

**Ответ:**
```json
{
  "id": "uuid",
  "agent_id": "uuid",
  "session_id": "uuid",
  "status": "succeeded",
  "input_message": "Hello...",
  "output_message": "The current weather in Moscow is sunny, 22°C",
  "trace_id": "uuid",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:01Z",
  "prompt_tokens": 150,
  "completion_tokens": 50,
  "total_tokens": 200,
  "tools_called": [
    {
      "name": "weather_api",
      "tool_call_id": "call_123",
      "args": {"city": "Moscow"}
    }
  ]
}
```

#### `POST /runs/stream`
Потоковый запуск агента с SSE.

**Формат SSE:**
```
event: start
data: {"run_id": "uuid", "trace_id": "uuid"}

event: result
data: {"output": "Agent response text"}

event: error
data: {"error": "Error message"}
```

#### `GET /runs/{run_id}`
Получение результата запуска.

#### `DELETE /runs/session/{session_id}`
Удаление всей истории `run` по одному `session_id`, чтобы очистить контекст диалога.

### Здоровье системы (`/health`)

#### `GET /health`
Проверка здоровья сервиса.

**Ответ:**
```json
{
  "status": "ok"
}
```

## Типы данных

### Agent
```typescript
interface Agent {
  id: UUID;
  tenant_id: UUID;
  owner_user_id: UUID;
  name: string;           // 1-200 символов
  system_prompt: string;  // Системный промпт
  model: string;          // Название модели (openai:gpt-4.1-mini, openai:gpt-4.1, etc.)
  llm_params?: object;    // Параметры для LLM
  status: "draft" | "published";
  version: number;
  created_at: DateTime;
  updated_at?: DateTime;
}
```

### Tool
```typescript
interface Tool {
  id: UUID;
  tenant_id: UUID;
  name: string;           // 1-200 символов
  description: string;
  input_schema: JSONSchema; // JSON Schema для входных параметров
  execution_type: "http_webhook" | "internal";
  endpoint?: string;      // URL для http_webhook
  auth_type: "none" | "api_key" | "oauth2" | "service";
  status: "active" | "deprecated";
  version: number;
  created_at: DateTime;
  updated_at?: DateTime;
}
```

### Binding
```typescript
interface AgentToolBinding {
  id: UUID;
  tenant_id: UUID;
  agent_id: UUID;
  tool_id: UUID;
  permission_scope: "read" | "write";
  timeout_ms: number;
  rate_limit?: string;    // Формат: "10/minute", "100/hour"
  allowed_domains: string[];
  secrets_ref?: string;   // Ссылка на секрет для аутентификации
}
```

### Run
```typescript
interface Run {
  id: UUID;
  tenant_id: UUID;
  agent_id: UUID;
  session_id: UUID;
  status: "running" | "succeeded" | "failed";
  input_message: string;
  output_message?: string;
  error_message?: string;
  trace_id: string;
  created_at: DateTime;
  updated_at?: DateTime;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  tools_called?: Array<{
    name: string;
    tool_call_id?: string;
    args: Record<string, any>;
  }>;
}
```

## Настройки окружения

### Основные настройки
```bash
# База данных
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Redis (для rate limiting)
REDIS_URL=redis://redis:6379/0

# Пул соединений БД
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT_SECONDS=30
DB_POOL_RECYCLE_SECONDS=1800

# JWT
JWT_SECRET=your-secret-key
JWT_ALGORITHM=HS256
JWT_AUDIENCE=agent-platform
JWT_ISSUER=agent-platform

# API ключи
API_KEY_PEPPER=pepper-string
ALLOW_TEST_TOKENS=false

# Rate limiting
RATE_LIMIT_DEFAULT=100/minute
RATE_LIMIT_RUNS=20/minute
RATE_LIMIT_AUTH_LOGIN=15/minute
RATE_LIMIT_AUTH_REFRESH=30/minute
RATE_LIMIT_AUTH_REGISTER=3/hour

# Anti brute-force для /auth/login (дополнительно к rate limit)
AUTH_LOGIN_BRUTEFORCE_ENABLED=true
AUTH_LOGIN_BRUTEFORCE_WINDOW_SECONDS=900
AUTH_LOGIN_BRUTEFORCE_PROGRESSIVE_ENABLED=true
AUTH_LOGIN_BRUTEFORCE_BASE_BLOCK_SECONDS=60
AUTH_LOGIN_BRUTEFORCE_MAX_BLOCK_SECONDS=7200
AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_IP=40
AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_EMAIL=10
AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_IP_EMAIL=5
# /24 имеет риск ложных срабатываний за NAT, поэтому по умолчанию отключен.
AUTH_LOGIN_BRUTEFORCE_SUBNET_ENABLED=false
AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_SUBNET=120
```

### Настройки инструментов
```bash
# PydanticAI (доступны: gpt-4.1, gpt-4.1-mini, gpt-4.1-nano, gpt-5.2, и др.)
PYDANTICAI_DEFAULT_MODEL=openai:gpt-4.1-mini

# Таймауты инструментов
TOOL_DEFAULT_TIMEOUT_MS=15000
TOOL_MAX_TIMEOUT_MS=60000
TOOL_RETRY_ATTEMPTS=2

# SSE
SSE_KEEPALIVE_SECONDS=15
```

### Аутентификация API ключей (для админов)
```bash
AUTH_API_KEYS='{
  "admin-key-123": {
    "tenant_id": "00000000-0000-0000-0000-000000000001",
    "user_id": "00000000-0000-0000-0000-000000000002",
    "scopes": ["tools:read", "tools:write"]
  }
}'
```

## Безопасность

### Аутентификация
- **JWT токены**: Bearer токены в заголовке `Authorization`
- **API ключи**: В заголовке `x-api-key` или теле запроса
- **Тестовые токены**: Только в dev окружении

### Авторизация
- **Scopes**: `tools:read`, `tools:write`
- **Многоарендность**: Полная изоляция по `tenant_id`
- **Мягкое удаление**: Данные не удаляются физически

### Rate Limiting
- Настраиваемые лимиты по эндпоинтам
- Redis-based хранение состояния
- Возврат HTTP 429 при превышении

### Безопасность инструментов
- **Валидация доменов**: Белый список разрешенных доменов
- **Секреты**: Хранение API ключей в переменных окружения
- **Таймауты**: Защита от зависших запросов
- **Повторные попытки**: Автоматическое повторение при ошибках
- **Trace ID**: Отслеживание всех вызовов

### Аудит
- Полное логирование всех действий
- Trace ID для отслеживания запросов
- Idempotency keys для предотвращения дублирования

## Развертывание

### Docker Compose (рекомендуется)

Текущий production-стек использует Caddy как reverse proxy и отдельный контейнер frontend.

```yaml
services:
  caddy:
    image: caddy:2.10-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config

  frontend:
    build:
      context: ../frontend
      args:
        NUXT_PUBLIC_API_BASE: /api/v1
        NUXT_PUBLIC_SITE_URL: https://lk.chatmedbot.ru
        NUXT_PUBLIC_DOMAIN: lk.chatmedbot.ru

  api:
    build:
      context: .
    expose:
      - "8000"
    depends_on:
      - db
      - redis
    cpus: "${API_CPUS:-2.0}"
    mem_limit: "${API_MEM_LIMIT:-1024m}"

  db:
    image: pgvector/pgvector:pg16

  redis:
    image: redis:7
```

### VPS развертывание

1. Настройте DNS A-записи:
   - `api.chatmedbot.ru` -> IP VPS
   - `lk.chatmedbot.ru` -> IP VPS
2. Установите Docker Engine и Compose plugin:
   ```bash
   sudo bash /opt/myapp/infra/scripts/install-docker-ubuntu.sh
   ```
3. Перейдите в инфраструктурную папку:
   ```bash
   cd /opt/myapp/infra
   ```
4. Скопируйте `env.example` в `.env` и задайте минимум:
   - `ACME_EMAIL`
   - `POSTGRES_*`
   - `JWT_SECRET`, `API_KEY_PEPPER`, `OPENAI_API_KEY`
5. Запустите стек:
   ```bash
   docker compose up -d --build
   docker compose exec api alembic upgrade head
   ```
6. Проверьте доступность:
   - `https://api.chatmedbot.ru/api/v1/health`
   - `https://lk.chatmedbot.ru`

## Разработка

### Структура проекта

```
backend/
├── app/
│   ├── api/
│   │   ├── routers/          # API эндпоинты
│   │   └── deps.py          # Зависимости FastAPI
│   ├── core/                # Конфигурация и утилиты
│   │   ├── config.py        # Настройки Pydantic
│   │   ├── limiter.py       # Rate limiting
│   │   ├── logging.py       # Логирование
│   │   └── security.py      # Безопасность
│   ├── db/
│   │   ├── models/          # SQLAlchemy модели
│   │   ├── session.py       # БД сессии
│   │   └── base.py          # Базовые классы
│   ├── schemas/             # Pydantic схемы
│   ├── services/            # Бизнес-логика
│   └── main.py              # Точка входа
├── alembic/                 # Миграции БД
├── Dockerfile
└── requirements.txt
```

### Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск PostgreSQL и Redis
docker run -d -p 5432:5432 -e POSTGRES_DB=agents postgres:15
docker run -d -p 6379:6379 redis:7-alpine

# Миграции
alembic upgrade head

# Запуск сервера
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Тестирование

```bash
# Создание агента
curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "TestAgent", "model": "openai:gpt-4.1-mini"}'

# Создание инструмента
curl -X POST http://localhost:8000/tools \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "echo",
    "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
    "execution_type": "http_webhook",
    "endpoint": "http://tool-mock:9000/echo"
  }'

# Запуск агента
curl -X POST http://localhost:8000/runs \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"agent_id": "...", "input_message": "Echo hello"}'
```

## Мониторинг и логирование

### Логирование
- **Structlog**: Структурированное логирование
- **Trace ID**: Отслеживание запросов через всю систему
- **Уровни**: DEBUG, INFO, WARNING, ERROR

### Мониторинг соединений к БД

#### Проверка состояния через API
```bash
# Быстрая проверка всех endpoints
python scripts/check_production.py

# Или вручную:
# Базовая проверка здоровья
curl https://agentsapp.integration-ai.ru/health

# Детальная информация о БД и пуле соединений
curl https://agentsapp.integration-ai.ru/health/db
```

#### Мониторинг через скрипт
```bash
# Production мониторинг (обновляется каждые 30 секунд)
./scripts/monitor_production.sh

# Интерактивный dashboard с цветовым кодированием
python scripts/db_dashboard.py
# или с кастомными настройками:
API_URL=https://agentsapp.integration-ai.ru REFRESH_INTERVAL=10 python scripts/db_dashboard.py

# Локальный мониторинг (для разработки)
./scripts/monitor_db_connections.sh
```

#### Проверка через PostgreSQL
```sql
-- Количество активных соединений
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Все соединения с деталями
SELECT datname, usename, client_addr, state, query_start
FROM pg_stat_activity;

-- Максимальное количество соединений
SHOW max_connections;
```

#### Тестирование нагрузки
```bash
# Тест с 20 параллельными запросами в течение 30 секунд
python scripts/load_test_db.py https://agentsapp.integration-ai.ru 20 30

# Легкий тест для проверки работоспособности
python scripts/load_test_db.py https://agentsapp.integration-ai.ru 5 10
```

### Настройка алертинга

**Критические метрики для мониторинга:**
- `usage_percent > 80%` - близок лимит соединений
- `active_connections > pool_size + max_overflow` - переполнение пула
- Время выполнения запросов > 2 секунд

### Метрики
- **Health check**: `/health` эндпоинт
- **Rate limiting**: Redis-based счетчики
- **Аудит**: Полное логирование действий

### Отладка
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI схема**: `http://localhost:8000/openapi.json`

## Расширяемость

### Добавление новых типов инструментов

```python
# В app/services/tool_executor.py
async def execute_tool_call(...):
    if auth_type == "oauth2":
        # Реализовать OAuth2 flow
        pass
    elif auth_type == "service":
        # Service-to-service auth
        pass
```

### Кастомные модели агентов

```python
# В app/services/runtime.py
def _build_agent(model_name: str, system_prompt: str, llm_params: dict):
    if model_name.startswith("custom:"):
        # Кастомная логика для модели
        return CustomAgent(model_name, system_prompt, llm_params)
    # Стандартная логика
    return PydanticAgent(model_name, system_prompt=system_prompt)
```

### Новые эндпоинты

```python
# В app/api/routers/agents.py
@router.post("/{agent_id}/clone")
async def clone_agent(agent_id: UUID, ...):
    # Логика клонирования агента
    pass
```

## Архитектурные решения

### Многоарендность (Multi-tenancy)
- **Tenant ID**: UUID для каждого арендатора
- **Изоляция**: Полная изоляция данных на уровне запросов
- **API ключи**: Привязка к конкретному tenant и user

### Асинхронность
- **FastAPI**: Асинхронный веб-фреймворк
- **SQLAlchemy**: Async сессии для БД
- **HTTPx**: Асинхронные HTTP запросы к инструментам

### Безопасность
- **JWT**: Stateless аутентификация
- **Rate limiting**: Защита от DoS атак
- **Валидация**: JSON Schema для входных данных
- **Secrets**: Безопасное хранение API ключей

### Масштабируемость
- **Stateless API**: Горизонтальное масштабирование
- **Redis**: Кэширование и rate limiting
- **PostgreSQL**: Надежное хранение данных
- **Docker**: Контейнеризация для развертывания

## Будущие улучшения

### Планируемые возможности
- **WebSocket**: Реал-тайм коммуникация с агентами
- **Плагины**: Система плагинов для расширения функциональности
- **Метрики**: Prometheus метрики и Grafana dashboards
- **Кэширование**: Redis кэширование результатов
- **Queues**: Очереди для асинхронной обработки
- **UI**: Веб-интерфейс для управления агентами

### API версии
- **Версионирование**: Поддержка v1, v2+ API
- **Обратная совместимость**: Плавные миграции
- **Документация**: Версионированная документация

---

## Контрибьютинг

1. Fork репозиторий
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## Лицензия

Этот проект лицензирован под MIT License - смотрите файл [LICENSE](LICENSE) для деталей.

## Запуск локально (Docker)

1) Перейдите в инфраструктурную папку:
   ```bash
   cd /opt/myapp/infra
   ```
2) Скопируйте `env.example` в `.env` и при необходимости измените значения.
3) Запуск контейнеров:
   ```bash
   docker compose up -d --build
   ```
4) Примените миграции:
   ```bash
   docker compose exec api alembic upgrade head
   ```
5) Откройте Swagger:
   ```
   http://localhost:8000/docs
   ```

## Запуск на VPS (домены: api.chatmedbot.ru и lk.chatmedbot.ru)

1) Настройте DNS A-записи доменов на IP VPS:
   - `api.chatmedbot.ru`
   - `lk.chatmedbot.ru`
2) Установите Docker:
   ```bash
   sudo bash /opt/myapp/infra/scripts/install-docker-ubuntu.sh
   ```
3) Перейдите в папку инфраструктуры:
   ```bash
   cd /opt/myapp/infra
   ```
4) Скопируйте `env.example` в `.env` и обновите значения (`ACME_EMAIL`, `JWT_SECRET`, `API_KEY_PEPPER`, `OPENAI_API_KEY`).
5) Запуск:
   ```bash
   docker compose up -d --build
   docker compose exec api alembic upgrade head
   ```
6) Проверка:
   - `https://api.chatmedbot.ru/api/v1/health`
   - `https://lk.chatmedbot.ru`

### Балансировка ресурсов (CPU/RAM)

Распределение ресурсов задаётся через `.env`:

```bash
API_CPUS=2.0
API_MEM_LIMIT=1024m
API_MEM_RESERVATION=512m

FRONTEND_CPUS=0.50
FRONTEND_MEM_LIMIT=256m
FRONTEND_MEM_RESERVATION=128m

CADDY_CPUS=0.50
CADDY_MEM_LIMIT=256m
CADDY_MEM_RESERVATION=128m
```

Чтобы отдать больше ресурсов backend, увеличьте `API_CPUS`/`API_MEM_LIMIT` и уменьшите `FRONTEND_*`.

Caddy получает и обновляет TLS сертификаты автоматически, отдельный certbot не нужен.

## JWT

API ожидает `Authorization: Bearer <token>`.

Для прод‑тестирования используйте:
`POST /auth/token` с заголовком `x-api-key` или телом `{"api_key": "..."}`.
Ключи можно создавать через `POST /api-keys` (после авторизации JWT).

Тестовый токен доступен только в `dev` или при `ALLOW_TEST_TOKENS=true`:
`GET /auth/test-token`.

Минимальные claims:
```json
{
  "sub": "00000000-0000-0000-0000-000000000001",
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "scopes": ["tools:write"],
  "iss": "agent-platform",
  "aud": "agent-platform"
}
```

## Пример проверки run с tool

1) Создать tool:
```bash
curl -X POST http://localhost:8000/tools \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "echo_tool",
    "description": "Echoes input back",
    "input_schema": {
      "type": "object",
      "properties": { "text": { "type": "string" } },
      "required": ["text"]
    },
    "execution_type": "http_webhook",
    "endpoint": "http://tool-mock:9000/echo",
    "auth_type": "none"
  }'
```

2) Создать агента:
```bash
curl -X POST http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "EchoAgent",
    "system_prompt": "Use tools when needed.",
    "model": "openai:gpt-4.1-mini",
    "llm_params": { "temperature": 0.2 },
    "status": "published",
    "version": 1
  }'
```

3) Привязать tool к агенту:
```bash
curl -X POST http://localhost:8000/agents/{agent_id}/tools/{tool_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_scope": "read",
    "timeout_ms": 15000,
    "allowed_domains": ["tool-mock"]
  }'
```

4) Запустить run:
```bash
curl -X POST http://localhost:8000/runs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "{agent_id}",
    "input_message": "Echo the word hello using the tool"
  }'
```

## Примечания

- В `/opt/myapp/infra/docker-compose.yml` добавлен сервис `tool-mock` (HTTP `http://tool-mock:9000`).
- `input_schema` — JSON Schema для аргументов инструмента.
- Имена свойств в `input_schema.properties` должны быть валидными идентификаторами Python.
- `auth_type=api_key` использует `secrets_ref` из binding и загружает ключ из `ENV` (`SECRETS_REF` или `SECRET_<REF>`).
- Для `permission_scope=write` нужен scope `tools:write` в JWT.
- SSE поток доступен на `POST /runs/stream`.
- `allowed_domains` сравнивается по hostname (без схемы и пути).# agents-systems
