# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Что это за проект

Многотенантная платформа AI-агентов для медицинских клиник (**ChatMedBot**).
Агенты общаются с пациентами через Telegram/WhatsApp, понимают запросы на запись, выбирают услугу/специалиста через GraphRAG, затем оформляют запись через SQNS (CRM клиники).

Монорепозиторий: `backend/` (FastAPI), `frontend/` (Nuxt 3), `infra/` (Docker Compose).

---

## Стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI, PydanticAI 0.0.14, SQLAlchemy 2 async |
| База данных | PostgreSQL 16 + pgvector (asyncpg) |
| Граф | Neo4j 5.22 (опционально), Microsoft GraphRAG (локальный) |
| Кэш/очереди | Redis 7 |
| Frontend | Nuxt 3, Vue 3, TypeScript, Tailwind, Pinia |
| Деплой | Gunicorn + UvicornWorker × 2, Caddy |
| LLM | OpenAI (gpt-4o-mini по умолчанию), кастомные провайдеры |
| Мониторинг | Structlog, Logfire, Netdata |

---

## Структура репозитория

```
backend/
  app/
    main.py                  # FastAPI app, lifespan, middleware
    core/config.py           # 140+ Pydantic settings
    db/models/               # 50+ SQLAlchemy моделей
    api/routers/             # REST-эндпоинты
      agents/                # CRUD агентов, каналы, SQNS, знания, потоки
      integrations.py        # Публичный API (x-api-key)
      webhooks.py            # Telegram/WhatsApp webhook handlers
      webhooks_inbound_agent.py  # Общая логика: входящее сообщение → агент
      ws.py                  # WebSocket для стриминга
    services/
      runtime/               # Исполнение агентов (PydanticAI)
        orchestrator.py      # Главный цикл агента
        microsoft_graphrag_tool.py  # GraphRAG поиск + SQNS матчинг
        tool_registry.py     # Сборка тулов по категориям
        sqns.py              # Тулы записи (SQNS)
        tools.py             # knowledge, direct_questions, directory тулы
        context_assembler.py # Выбор категорий для агента
        scenario_runtime.py  # Function rules + augmented prompt перед/после LLM
      message_debounce.py    # Буферизация быстрых сообщений в Redis
      dialog_state.py        # Статус диалогов (active/paused/disabled)
      sqns/                  # Синхронизация с CRM клиники
      graphrag_export/       # Экспорт и индексация GraphRAG
      script_flow_*.py       # Компиляция Vue Flow графов в инструкции LLM
      knowledge_files.py     # Загрузка и индексация документов
      direct_questions/      # Семантический поиск по Q&A
      directory/             # Семантический поиск по справочникам
      function_rules_runtime.py  # Условная логика до/после LLM
    workers/                 # Фоновые задачи
      sqns_hourly_sync.py
      direct_questions_embedding_retry.py
      direct_questions_followup_dispatch.py
      scenario_delayed_dispatch.py
      script_flow_index.py
  alembic/                   # 105+ миграций
  tests/                     # Pytest тесты

frontend/
  pages/                     # Nuxt файловый роутинг
  components/                # UI + доменные компоненты
  composables/               # API слой + Pinia stores
  types/                     # TypeScript интерфейсы

infra/
  docker-compose.yml         # 10+ сервисов
  .env                       # Секреты (не в git)
  data/graphrag/             # GraphRAG индексы по tenant/agent
```

---

## Запуск и разработка

### Docker (основной способ)

```bash
cd infra
cp env.example .env          # заполнить секреты
docker compose up -d --build
curl http://localhost:8000/api/v1/health
```

Миграции применяются автоматически через `entrypoint.sh` при старте контейнера.
Обойти: `SKIP_ALEMBIC=1`.

**После изменений Python-кода** — обязательный рестарт (Gunicorn без `--reload`):
```bash
docker compose restart api
```

### Backend без Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend без Docker

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### Тесты

```bash
cd backend
python -m pytest tests/ -v
python -m pytest tests/path/to/test_file.py::test_name -v  # один тест
```

---

## База данных

**Прямое подключение** (из этого окружения):
```
host: 172.18.0.4
port: 5432
user: postgres
password: <из infra/.env → POSTGRES_PASSWORD>
db: agents
```

Python-пример:
```python
import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect(
        host="172.18.0.4", port=5432,
        user="postgres", password="<пароль>",
        database="agents"
    )

asyncio.run(main())
```

Используй `/opt/myapp/backend/.venv/bin/python` — там есть asyncpg.

### Ключевые таблицы

| Таблица | Что хранит |
|---|---|
| `agents` | Агенты: system_prompt, model, sqns_*, graphrag_* |
| `runs` | Запуски: input/output, токены, tools_called, status |
| `session_messages` | История диалога в формате PydanticAI |
| `dialog_states` | Статус диалога: active/paused/disabled, last_user_message_at, last_manager_message_at |
| `agent_user_states` | Статус per-user per-platform (telegram/whatsapp — disable/block) |
| `sqns_services` | Кэш услуг из SQNS (синк раз в час) |
| `sqns_resources` | Кэш специалистов из SQNS |
| `script_flows` | Vue Flow графы сценариев |
| `knowledge_files` | Загруженные документы с чанками и эмбеддингами |
| `direct_questions` | Q&A пары с эмбеддингами |
| `function_rules` | Условные правила (фазы: before_llm, after_llm, manager_message) |
| `tenant_balances` | Баланс токенов/рублей по тенанту |

### Миграции
```bash
alembic revision --autogenerate -m "описание"
alembic upgrade head
alembic downgrade -1
```

---

## API

### Публичный (Integration) API

```
POST /api/v1/integrations/chat
Header: x-api-key: <ключ агента>
Body: {"message": "текст", "session_id": "произвольный-id"}
```

Возвращает: `{response, session_id, run_id, tool_names}`.

### Внутренний API

Все эндпоинты за JWT. Swagger: `http://localhost:8000/docs`.

```
GET  /api/v1/health
POST /api/v1/runs                                         # запустить агента
POST /api/v1/runs/stream                                  # стриминг (SSE)
GET  /api/v1/agents/{id}/runs                             # история запусков
GET  /api/v1/agents/{id}/dialogs/{dialog_id}/messages     # сообщения диалога
POST /api/v1/agents/{id}/dialogs/{dialog_id}/messages     # отправить (агент)
POST /api/v1/agents/{id}/dialogs/{dialog_id}/manager-message  # отправить (менеджер, без запуска агента)
DELETE /api/v1/agents/{id}/dialogs/{dialog_id}/history    # очистить историю
```

---

## Архитектура агента

### Путь входящего сообщения (Telegram/WhatsApp)

```
Telegram update
  → webhooks.py: проверка channel, dialog_active, manager_paused, user_disabled
  → message_debounce.py: буферизует сообщение в Redis, ждёт (3–10 сек)
    └ если за это время пришли ещё сообщения — объединяет их в одно
  → webhooks_inbound_agent.py: сохраняет user_message, запускает агента
  → scenario_runtime.py: выполняет FunctionRule (фаза before_llm)
    └ может добавить блоки в system_prompt, вернуть ready-reply без LLM
  → orchestrator.py (PydanticAI agent)
  → context_assembler.py: выбирает категории тулов по контексту диалога
  → tool_registry.py: собирает тулы: knowledge, sqns, graphrag...
  → LLM вызов
  → tool calls:
      query_microsoft_graphrag  → GraphRAG + SQNS fuzzy match
      sqns_find_booking_options → CRM: подбор услуги
      sqns_list_slots           → CRM: слоты
      sqns_create_visit         → CRM: запись
      search_knowledge          → pgvector поиск
      search_direct_questions   → Q&A поиск
  → scenario_runtime.py: FunctionRule (фаза after_llm)
  → output_message → session_messages, Run
  → send_telegram_message → клиент
```

### Сообщение менеджера (из интерфейса)

```
POST /manager-message
  → сохраняется в session_messages с role="manager"
  → broadcast через WebSocket на фронт
  → отправляется клиенту через Telegram/WhatsApp (outbound)
  → агент НЕ запускается
  → устанавливает last_manager_message_at → auto-pause агента
```

### GraphRAG tool (`microsoft_graphrag_tool.py`)

- `focus=booking` — ищет услуги/специалистов, возвращает `suggested_sqns_args`
- `focus=general` — широкий поиск по графу (для возражений, контекста)
- Источники: Neo4j граф → workspace preview → SQNS таблицы
- Скрипт-флоу индексируется в граф: узлы с `entity_type=objection/concern/tactic`
- `_strip_service_code()` — убирает медкоды типа А11.01.12 из названий услуг

### Debounce входящих сообщений (`message_debounce.py`)

Короткие сообщения (<20 символов) ждут **10 сек**, средние (<80) — **6 сек**, длинные — **3 сек**. Если за это время приходит ещё одно сообщение — версия меняется, старая задача отменяется, текст объединяется. Telegram получает `200 OK` немедленно, агент запускается через `asyncio.create_task`.

---

## Ключевые настройки (config.py)

```python
runtime_tool_calls_limit = 10   # максимум tool-вызовов за один run
runtime_request_limit = 11      # максимум LLM-запросов (≥ tool_calls + 1)
pydanticai_default_model        # модель по умолчанию для всех агентов
summary_model                   # модель для суммаризации истории
direct_questions_rerank_enabled # reranking Q&A результатов
```

---

## Соглашения

### Python
- Всё async/await (FastAPI + SQLAlchemy async)
- Модели: UUID primary keys, `TimestampMixin` (created_at/updated_at)
- Мягкое удаление: `SoftDeleteMixin` (deleted_at)
- Логирование: `structlog.get_logger(__name__)`
- Ошибки: стандартные JSON-ответы `{"error": "...", "message": "..."}`
- Мультитенантность: всегда фильтруй по `tenant_id`

---

## Важные агенты в БД

| UUID | Имя | Особенности |
|---|---|---|
| `176548eb-cce1-4ca8-8775-1f24d45a1b6d` | FACE CLINIC | Стилия, биоревитализация, SQNS, GraphRAG |

---

## Внешние интеграции

| Сервис | Назначение | Ключевые файлы |
|---|---|---|
| **SQNS** | CRM клиники: услуги, специалисты, запись | `services/sqns/`, `runtime/sqns.py` |
| **OpenAI** | LLM + эмбеддинги | `runtime/model_resolver.py` |
| **Wappi** | WhatsApp | `services/wappi/` |
| **Telegram** | Бот + алерты | `services/telegram.py` |
| **Neo4j** | Граф (опционально) | `runtime/neo4j_client.py` |
| **Logfire** | Мониторинг стоимости | `main.py`, `services/logfire_cost_reconcile.py` |

---

## Частые задачи

### Прочитать/обновить промпт агента
```python
await conn.fetchval("SELECT system_prompt FROM agents WHERE id = $1", agent_id)
await conn.execute("UPDATE agents SET system_prompt = $1 WHERE id = $2", new_prompt, agent_id)
```

### Посмотреть последние runs агента
```sql
SELECT id, status, input_message, output_message, prompt_tokens, completion_tokens, created_at
FROM runs
WHERE agent_id = '<uuid>'
ORDER BY created_at DESC
LIMIT 10;
```

### Проверить статус Telegram webhook
```python
import httpx
r = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo")
print(r.json()['result'])
```

### Сбросить очередь Telegram (при Connection timed out)
Если `pending_update_count > 0` после ошибки — сброс через переустановку webhook:
```python
httpx.post(f"https://api.telegram.org/bot{token}/setWebhook",
    data={"url": webhook_url, "drop_pending_updates": "true", "secret_token": secret})
```

### Тестировать агента через API
```bash
curl -s -X POST http://localhost:8000/api/v1/integrations/chat \
  -H "Content-Type: application/json" \
  -H "x-api-key: <ключ>" \
  -d '{"message": "текст", "session_id": "test-001"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['response']); print('tools:', d['tool_names'])"
```
