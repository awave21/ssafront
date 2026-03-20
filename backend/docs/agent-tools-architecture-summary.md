# Обзор архитектуры агентов и тулов

**Дата**: 2026-01-26  
**Статус**: ✅ Критические задачи выполнены, проект стабилен

## 1. Контекст
- Основная цель — добиться, чтобы агенты всегда получали свой системный prompt, работали с безопасными туловами через MCP и использовали предсказуемые параметры LLM.
- Наблюдались проблемы: system prompt не вставлялся после фильтрации истории, `exec()` генерировал небезопасные тул-обёртки, SQNS тулы были захардкожены, валидация отсутствовала, debug-логи писались в файл.
- Архитектурный анализ и дорожная карта по-прежнему живут в `docs/architecture-analysis-agents-tools.md`.

## 2. Что сделано (критические исправления)

### 2.1. Надёжный system prompt
- История фильтруется по `part_kind='system-prompt'`, а затем мы явно вставляем `SystemPromptPart` с текстом `agent.system_prompt` перед запуском модели.
- Это устраняет дублирование и гарантирует, что агент получает нужный prompt даже при перезапуске или наличии истории сообщений.

### 2.2. Безопасные туловы через `PydanticTool`
- `_wrap_tool_signature()` и любые `exec()`-фрагменты удалены из `runtime.py`.
- Каждый тул строится с `PydanticTool.from_schema()`, обёртки описываются как асинхронные функции с корректными типами и документацией.
- Стек исключений становится понятнее, type checkers работают, атаки через выполнение произвольного кода невозможны.

### 2.3. FastMCP + SQNS
- `fastmcp>=0.3.0` добавлен в `backend/requirements.txt`.
- Новый `backend/app/services/sqns_mcp_server.py` описывает SQNS методы через `@mcp.tool()` и возвращает `FastMCPToolset`.
- `runtime.py` умеет подключать `FastMCPToolset` к агентам и содержит legacy-фоллбек на случай отсутствия зависимостей.
- Это делает SQNS туловы MCP-совместимыми и упрощает добавление новых инструментов.

### 2.4. Валидация схем и параметров
- В `backend/app/schemas/tool.py` добавлен `@field_validator('input_schema')`, который проверяет Draft 2020-12, требует `type='object'` и валидные идентификаторы полей.
- В `backend/app/schemas/agent.py` введена модель `LLMParams` с ограничениями (`temperature` 0–2, `max_tokens` 1–100000, `top_p`, `top_k`, `frequency_penalty`, `presence_penalty`, `stop`, `seed`), а `llm_params` проходит эту валидацию.
- Такие проверки исключают сохранить некорректный JSON в базу.

### 2.5. Структурированное логирование
- `backend/app/main.py`, `backend/app/api/routers/agents.py` и `backend/app/api/routers/health.py` больше не пишут в `/root/agentsapp/.cursor/debug.log`.
- Вместо этого используется `logger.info()` и `logger.error()` (structlog), поэтому логи видно напрямую через `docker logs`.

## 3. Проверки и запуск
- `docker compose restart api` — контейнер перезапущен без ошибок.
- `docker compose logs api --tail 30` — FastMCP стартует, речь о запуске без WARN/ERROR.
- `ReadLints backend/app/schemas/tool.py backend/app/schemas/agent.py` — нет предупреждений.
- `health`/`db health` эндпоинты возвращают `status: ok`.

## 4. Изменённые файлы (Phase 1)
1. `backend/requirements.txt` — `fastmcp>=0.3.0`, `jmespath>=1.0`
2. `backend/app/services/runtime.py` — рефакторинг тулов, FastMCP, system prompt
3. `backend/app/services/sqns_mcp_server.py` — новый MCP сервер
4. `backend/app/schemas/tool.py` — валидатор JSON Schema + новые поля + ToolTestRequest/ToolTestResponse
5. `backend/app/schemas/agent.py` — модель `LLMParams`, валидация `llm_params`, ограничение `max_history_messages`
6. `backend/app/api/routers/agents.py`, `backend/app/main.py`, `backend/app/api/routers/health.py` — удалено debug-логирование и заменено structlog

## 5. HTTP Tool Enhancements (2026-02-10)

### 5.1. Новые поля модели Tool

В таблицу `tools` добавлены 4 новых колонки (миграция `0030_tool_http_enhancements`):

| Поле | Тип | Default | Описание |
|------|-----|---------|----------|
| `http_method` | `String(10)` | `"POST"` | HTTP метод: GET, POST, PUT, PATCH, DELETE |
| `custom_headers` | `JSONB` | `null` | Статические заголовки: `{"Accept": "application/json", "X-Custom": "value"}` |
| `parameter_mapping` | `JSONB` | `null` | Куда размещать каждый параметр: `{"user_id": "path", "q": "query", "data": "body"}` |
| `response_transform` | `JSONB` | `null` | Фильтрация ответа для экономии токенов (режимы: `fields`, `jmespath`) |

### 5.2. Полная цепочка обработки

```
Фронт (создание tool) → ToolCreate schema → Tool DB model → Tool DB table
                                                    ↓
Агент вызывает tool → runtime_tools._tool_impl() → execute_tool_call()
                                                        ↓
                                               1. _split_params() → path/query/body
                                               2. custom_headers → headers
                                               3. auth → headers/query
                                               4. httpx.request(method, url, ...)
                                               5. transform_response(raw, config)
                                                        ↓
                                               Результат → агенту (LLM)
```

### 5.3. Файлы

| Файл | Что изменено |
|------|-------------|
| `alembic/versions/0030_tool_http_enhancements.py` | Миграция: 4 новых колонки |
| `app/db/models/tool.py` | Модель: `http_method`, `custom_headers`, `response_transform`, `parameter_mapping` |
| `app/schemas/tool.py` | Схемы: ToolBase/ToolUpdate + ToolTestRequest/ToolTestResponse |
| `app/api/routers/tools.py` | API: валидация + `POST /tools/test` + `POST /tools/{id}/test` |
| `app/api/routers/bindings.py` | API: `GET /agents/{id}/tools/details` (bindings + tool data) |
| `app/schemas/binding.py` | Схема: `BindingWithToolRead` с forward ref + model_rebuild() |
| `app/services/tool_executor.py` | Логика: `_split_params()`, `_pick_fields()`, `transform_response()`, `execute_tool_test()` |
| `app/services/runtime_tools.py` | Runtime: передача `http_method`, `custom_headers`, `parameter_mapping` + transform |

### 5.4. API Endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `POST /tools` | Создание | Принимает все новые поля |
| `PUT /tools/{id}` | Обновление | Принимает все новые поля |
| `GET /tools` | Список | Возвращает все новые поля |
| `POST /tools/test` | Тест inline | Тестирование tool без сохранения |
| `POST /tools/{id}/test` | Тест saved | Тестирование сохранённого tool |
| `GET /agents/{id}/tools/details` | Tools агента | Bindings + полные данные Tool |

## 6. x-fromAI: фильтрация параметров для LLM (2026-02-11)

### 6.1. Суть

Фронтенд помечает параметры инструмента флагом `x-fromAI`:
- `x-fromAI: true` — параметр заполняет LLM из контекста диалога (например `patient_name`)
- Без `x-fromAI` (или `false`) + `default` — статический параметр, который подставляется автоматически (например `api_version: "v2"`)

Бэкенд обрабатывает это в двух местах:
1. **Формирование схемы для LLM** — `_build_llm_schema()` фильтрует `input_schema`, оставляя только AI-параметры
2. **Выполнение tool call** — `_merge_tool_args()` мержит аргументы от LLM со статическими default

### 6.2. Защита

Валидатор `input_schema` в `schemas/tool.py` проверяет при создании/обновлении:
- `x-fromAI` должен быть boolean (защита от `"true"`, `1` и т.д.)
- Статический параметр (без `x-fromAI: true`) обязан иметь `default` — иначе он потеряется при выполнении

### 6.3. Обратная совместимость

Если ни одно свойство не имеет `x-fromAI` — поведение не меняется (функции возвращают оригинальные данные).

### 6.4. Файлы

| Файл | Что изменено |
|------|-------------|
| `app/services/runtime_tools.py` | `_build_llm_schema()`, `_merge_tool_args()`, изменён `_build_tool_wrapper` |
| `app/schemas/tool.py` | Валидация `x-fromAI` (boolean check + static default check) |

## 7. Изоляция истории сообщений по agent_id (2026-02-11)

### 7.1. Проблема

При использовании одного Telegram user для общения с несколькими агентами возникала **утечка контекста** между агентами:
- Таблица `session_messages` не содержала колонку `agent_id`
- Функция `_get_session_history()` загружала историю только по `session_id` и `tenant_id`
- Когда пользователь `telegram:306597938` общался с агентом "ТЕСТ" (d7504409), он получал **всю историю** этого user, включая 84 сообщения от агента "Фейс клиник" (176548eb)
- Агент видел чужие system prompts, туллы и контекст диалогов

### 7.2. Решение

Добавлена фильтрация истории по `agent_id` через JOIN с таблицей `runs`:

```python
async def _get_session_history(
    db: AsyncSession,
    session_id: str,
    tenant_id: UUID,
    agent_id: UUID,  # ← Новый параметр
    limit: int = 10,
) -> list[Any] | None:
    stmt = (
        select(SessionMessage.message)
        .join(Run, SessionMessage.run_id == Run.id)  # ← JOIN
        .where(
            SessionMessage.session_id == session_id,
            SessionMessage.tenant_id == tenant_id,
            Run.agent_id == agent_id,  # ← Фильтр по agent_id
        )
        # ...
    )
```

### 7.3. Измененные файлы

| Файл | Изменения |
|------|-----------|
| `app/api/routers/runs.py` | `_get_session_history()` - добавлен параметр `agent_id` и JOIN с `runs` |
| `app/api/routers/runs.py` | `create_run()` - передача `agent.id` в `_get_session_history()` |
| `app/api/routers/runs.py` | `stream_run()` - передача `agent.id` в `_get_session_history()` |
| `app/api/routers/webhooks.py` | `_process_telegram_message()` - передача `agent.id` |
| `app/api/routers/ws.py` | `_run_agent_and_send()` - передача `agent.id` |

### 7.4. Результат

- **Полная изоляция** агентов: каждый видит только свою историю диалога с пользователем
- **Безопасность**: нет утечки промптов, тулов и контекста между агентами
- **Обратная совместимость**: старые данные продолжают работать через связь `session_messages.run_id → runs.agent_id`

## 8. Следующие шаги
1. **Rate limiting** — реализовать проверку `binding.rate_limit` и сокращение частоты вызовов тулов.
2. **Кеширование SQNS** — кешировать `list_resources` / `find_client_by_phone` через `lru_cache` или Redis.
3. **Async queue для runs** — вынести работу `run_agent_with_tools` в Celery/RQ или background task.
4. **Удалить legacy-fallback** после завершения тестов FastMCP при уверенности в окружении.

## 9. Вывод
- Критические проблемы безопасности и архитектуры закрыты: system prompt стабилен, туловы безопасны, SQNS работает через MCP, агенты изолированы по истории сообщений.
- Валидные JSON-схемы и структурированное логирование упрощают поддержку.
- Этот документ теперь является центральной точкой для описания проделанных работ; отдельные резюме больше не нужны.

## 10. Источники
- Детальный анализ архитектуры и рекомендации — `docs/architecture-analysis-agents-tools.md`.
