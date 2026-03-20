# SQNS Integration Flow - Как работает подключение интеграции к агенту

## Краткий ответ

**✅ ДА**, при включении интеграции SQNS:

1. ✅ Инструменты **правильно подключаются к конкретному агенту** по `agent_id`
2. ✅ **Системный промпт агента передается** в каждый запрос
3. ✅ **История сообщений (message_history) передается** для поддержки контекста диалога

---

## Детальный Flow

### 1. Включение SQNS интеграции для агента

Когда вы включаете SQNS интеграцию через API:

```bash
POST /agents/{agent_id}/sqns/enable-by-password
{
  "host": "crmexchange.1denta.ru",
  "email": "user@example.com",
  "password": "password"
}
```

**Что происходит:**

```python
# backend/app/api/routers/agents.py

# 1. Получаем токен из SQNS
token = await fetch_token_by_login(host, email, password)

# 2. Создаем credential для этого агента
credential = Credential(
    tenant_id=user.tenant_id,
    name=f"SQNS for {agent.name}",
    auth_type="bearer",
    config=encrypt_config({"token": token}),
    is_active=True
)

# 3. Привязываем credential к КОНКРЕТНОМУ агенту
agent.sqns_enabled = True
agent.sqns_configured = True
agent.sqns_host = host
agent.sqns_credential_id = credential.id  # ← ПРИВЯЗКА К АГЕНТУ!
agent.sqns_status = "ok"
```

**Результат:**

- ✅ SQNS credential привязан к конкретному `agent_id`
- ✅ Разные агенты могут иметь разные SQNS интеграции

---

### 2. Запуск агента (Run) с SQNS инструментами

Когда пользователь отправляет сообщение агенту:

```bash
POST /runs
{
  "agent_id": "dc7a2d54-983c-4143-be9b-3082242c207b",
  "input_message": "Какие специалисты у вас работают?",
  "session_id": "optional-session-uuid"
}
```

#### Шаг 2.1: Загрузка агента из БД

```python
# backend/app/api/routers/runs.py:163

async def create_run(...):
    # Загружаем КОНКРЕТНОГО агента по agent_id
    agent, tools, bindings = await _load_agent_and_tools(
        db,
        payload.agent_id,  # ← ID конкретного агента
        user.tenant_id
    )

    # agent теперь содержит:
    # - agent.id
    # - agent.system_prompt  ← системный промпт
    # - agent.sqns_enabled
    # - agent.sqns_host
    # - agent.sqns_credential_id
    # - agent.max_history_messages
```

#### Шаг 2.2: Загрузка истории сообщений

```python
# backend/app/api/routers/runs.py:166

# Загружаем историю сообщений для session_id
session_id = payload.session_id or str(uuid4())
message_history = await _get_session_history(
    db,
    session_id,
    user.tenant_id,
    limit=agent.max_history_messages  # ← лимит из настроек агента
)

# message_history содержит:
# - Предыдущие сообщения пользователя
# - Предыдущие ответы агента
# - Предыдущие вызовы инструментов
# - НО: старые system prompts фильтруются (см. ниже)
```

#### Шаг 2.3: Подготовка SQNS инструментов

```python
# backend/app/services/runtime.py:273

async def run_agent_with_tools(agent, tools, bindings, ...):

    # Проверяем, включен ли SQNS для ЭТОГО агента
    if agent.sqns_enabled and agent.sqns_host and agent.sqns_credential_id:
        # ✅ SQNS включен для этого конкретного агента!

        # Вариант A: FastMCP (современный подход)
        if FASTMCP_AVAILABLE:
            sqns_client = await _build_sqns_client(agent, db, user)
            mcp_server = create_sqns_mcp_server(sqns_client)
            sqns_toolset = FastMCPToolset(mcp_server)

        # Вариант B: Legacy (если FastMCP недоступен)
        else:
            sqns_tools_definitions = get_sqns_tools_definitions()
            # Создаем инструменты, привязанные к agent.id
            for defn in sqns_tools_definitions:
                tool_fn = make_sqns_tool(...)
                wrapped_tools.append(tool_fn)
```

**Ключевой момент**: Каждый SQNS инструмент использует `agent.id` для получения правильного credential:

```python
# backend/app/services/runtime.py:303

async def _sqns_impl(**kwargs):
    # При каждом вызове инструмента:
    async with async_session_factory() as db:
        # Загружаем КОНКРЕТНОГО агента
        stmt = select(Agent).where(Agent.id == agent.id)
        agent_obj = (await db.execute(stmt)).scalar_one_or_none()

        # Строим SQNS client с credential ЭТОГО агента
        client = await _build_sqns_client(agent_obj, db, user)

        # Вызываем метод SQNS API
        return await method(**kwargs)
```

#### Шаг 2.4: Создание Agent с системным промптом

```python
# backend/app/services/runtime.py:389

# Создаем pydantic-ai Agent
pydantic_agent = _build_agent(
    model_name=agent.model,
    system_prompt=agent.system_prompt,  # ← СИСТЕМНЫЙ ПРОМПТ!
    llm_params=agent.llm_params or {},
    tools=wrapped_tools,                 # ← обычные tools + SQNS tools
    toolsets=sqns_toolsets               # ← SQNS MCP toolset (если FastMCP)
)
```

#### Шаг 2.5: Фильтрация старых system prompts

**ВАЖНО**: Если есть история сообщений, старые system prompts удаляются, чтобы использовался только **актуальный** системный промпт агента:

```python
# backend/app/services/runtime.py:409-429

if message_history:
    # Фильтруем старые SystemPromptPart из истории
    filtered_history = []
    removed_system_prompts = 0

    for msg in message_history:
        if hasattr(msg, "parts"):
            # Удаляем части с part_kind='system-prompt'
            new_parts = [
                p for p in msg.parts
                if getattr(p, "part_kind", None) != "system-prompt"
            ]
            removed_system_prompts += len(msg.parts) - len(new_parts)

            if new_parts:
                msg.parts = new_parts
                filtered_history.append(msg)

    logger.info("system_prompts_filtered", removed_system_prompts=removed_system_prompts)

    # Добавляем НОВЫЙ system prompt в начало истории
    if agent.system_prompt and filtered_history:
        system_prompt_message = ModelRequest(
            parts=[SystemPromptPart(agent.system_prompt)]
        )
        filtered_history.insert(0, system_prompt_message)

    message_history = filtered_history
```

**Почему это важно:**

- ✅ Гарантирует, что используется **актуальный** системный промпт
- ✅ Если вы изменили промпт агента, он применится к следующему сообщению
- ✅ История диалога сохраняется, но с обновленными инструкциями

#### Шаг 2.6: Выполнение агента

```python
# backend/app/services/runtime.py:430

result = await pydantic_agent.run(
    input_message,
    message_history=message_history  # ← История с актуальным system prompt
)

# Агент получает:
# 1. Актуальный system_prompt
# 2. Историю предыдущих сообщений (без старых system prompts)
# 3. Доступ к SQNS инструментам (если включены)
# 4. Входное сообщение пользователя
```

#### Шаг 2.7: Сохранение новых сообщений

```python
# backend/app/api/routers/runs.py:194

await _append_session_messages(
    db,
    user.tenant_id,
    session_id,
    run.id,
    new_messages,  # ← Новые сообщения включая вызовы SQNS tools
    agent.max_history_messages  # ← Автоматическая обрезка истории
)
```

---

## Схема данных

### Agent Model

```python
class Agent:
    id: UUID                           # Уникальный ID агента
    tenant_id: UUID                    # Tenant для изоляции
    name: str                          # Имя агента
    system_prompt: str                 # ← СИСТЕМНЫЙ ПРОМПТ
    model: str                         # Модель LLM
    llm_params: dict                   # Параметры модели

    # SQNS интеграция
    sqns_enabled: bool                 # ← Включена ли SQNS
    sqns_configured: bool              # ← Настроена ли SQNS
    sqns_host: str                     # ← Хост SQNS CRM
    sqns_credential_id: UUID           # ← Связь с Credential
    sqns_status: str                   # ok | error | disabled

    # История сообщений
    max_history_messages: int = 10     # ← Лимит истории
```

### Credential Model

```python
class Credential:
    id: UUID
    tenant_id: UUID
    name: str
    auth_type: str                     # "bearer" для SQNS
    config: bytes                      # Зашифрованный {"token": "..."}
    is_active: bool
```

### SessionMessage Model

```python
class SessionMessage:
    id: UUID
    tenant_id: UUID
    session_id: str                    # ← Группирует сообщения диалога
    run_id: UUID                       # Связь с Run
    message_index: int                 # Порядок в диалоге
    message: dict                      # ← Сериализованное сообщение pydantic-ai
```

---

## Ответы на ваши вопросы

### ✅ Правильно ли подключается к конкретному агенту?

**ДА!** SQNS интеграция привязана к конкретному агенту через:

1. **`agent.sqns_credential_id`** - каждый агент имеет свой SQNS credential
2. **Проверка при запуске**: `if agent.sqns_enabled and agent.sqns_host and agent.sqns_credential_id`
3. **Closure в инструментах**: каждый SQNS tool захватывает `agent.id` и использует его для получения credential

**Пример:**

```python
# Агент 1: стоматология
agent1.sqns_host = "crm.dentist.ru"
agent1.sqns_credential_id = credential_dentist.id

# Агент 2: косметология
agent2.sqns_host = "crm.beauty.ru"
agent2.sqns_credential_id = credential_beauty.id

# При вызове sqns_list_resources():
# - Агент 1 → запрос к crm.dentist.ru
# - Агент 2 → запрос к crm.beauty.ru
```

---

### ✅ Передается ли системный промпт?

**ДА!** Системный промпт передается в каждый запрос:

1. **При создании агента**: `pydantic_agent = _build_agent(..., system_prompt=agent.system_prompt)`
2. **Актуализация при истории**: Старые system prompts удаляются, новый добавляется в начало
3. **Логирование**: Система логирует `system_prompt_preview` для отладки

**Рекомендация для системного промпта:**

```python
agent.system_prompt = """
Ты — ассистент медицинской клиники с доступом к SQNS CRM системе.

ИНСТРУКЦИИ ПО ИСПОЛЬЗОВАНИЮ SQNS:
1. Когда пользователь спрашивает про специалистов → вызови sqns_list_resources()
2. Когда пользователь спрашивает про услуги → вызови sqns_list_services()
3. Для создания записи:
   - Найди клиента: sqns_find_client(phone="...")
   - Получи специалистов: sqns_list_resources()
   - Проверь слоты: sqns_list_slots(resource_id=..., date="...")
   - Создай запись: sqns_create_visit(resource_id=..., service_id=..., datetime=..., user_name=..., phone=..., email?=..., comment?=...)

КРИТИЧЕСКИ ВАЖНО:
- ВСЕГДА используй инструменты для получения данных
- НИКОГДА не придумывай информацию о специалистах или расписании
"""
```

---

### ✅ Передается ли история сообщений?

**ДА!** История сообщений передается для поддержки контекста:

1. **Загрузка истории**: `message_history = await _get_session_history(..., limit=agent.max_history_messages)`
2. **Фильтрация**: Старые system prompts удаляются, новый добавляется
3. **Передача в агент**: `await pydantic_agent.run(input_message, message_history=message_history)`
4. **Сохранение новых**: Новые сообщения автоматически добавляются в БД

**Лимит истории:**

- Настраивается через `agent.max_history_messages` (по умолчанию 10)
- Автоматическая обрезка старых сообщений при превышении лимита
- Группировка по `session_id` - разные диалоги не смешиваются

**Пример работы истории:**

```
# Запрос 1
User: "Какие специалисты у вас работают?"
Agent: [вызывает sqns_list_resources()] "У нас работают: Иванов, Петрова..."

# Сохраняется в session_messages:
# - ModelRequest с "Какие специалисты..."
# - ModelResponse с вызовом sqns_list_resources
# - ModelResponse с ответом агента

# Запрос 2 (тот же session_id)
User: "Запишите меня к Иванову"
Agent: [имеет контекст, что Иванов - специалист]
       [вызывает sqns_find_client, sqns_list_slots, sqns_create_visit]
       "Отлично, записал вас к Иванову..."

# История позволяет агенту:
# ✅ Знать, что "Иванов" - это специалист из предыдущего ответа
# ✅ Не спрашивать повторно, какой специалист нужен
# ✅ Использовать контекст диалога
```

---

## Диагностика и логирование

### Проверка подключения SQNS к агенту

```bash
# 1. Проверьте статус SQNS для агента
curl -X GET "https://agentsapp.integration-ai.ru/agents/{agent_id}/sqns/status" \
  -H "Authorization: Bearer TOKEN"

# Ожидается:
{
  "enabled": true,
  "configured": true,
  "host": "crmexchange.1denta.ru",
  "available_tools": [...]
}
```

### Логи при запуске агента

```bash
# Смотрим логи подключения SQNS
docker compose logs api | grep -A5 "sqns"

# Что искать:
# ✅ "sqns_toolset_prepared" - SQNS инструменты загружены
# ✅ "agent_created_with_tools" - агент создан с инструментами
# ✅ "sqns_list_resources" - вызов SQNS инструмента
# ✅ "system_prompt_preview" - проверка системного промпта
# ✅ "filtering_system_prompts_from_history" - фильтрация старых промптов
```

### Логи передачи истории

```bash
# Проверка истории сообщений
docker compose logs api | grep "history"

# Что искать:
# ✅ "filtering_system_prompts_from_history" - фильтрация
# ✅ "removed_system_prompts" - количество удаленных
# ✅ "new_system_prompt_prepended" - новый промпт добавлен
# ✅ "has_message_history" - история передана
```

---

## Частые проблемы и решения

### Проблема: Агент не использует SQNS инструменты

**Причины:**

1. ❌ `sqns_enabled=false` - интеграция не включена
2. ❌ `sqns_credential_id=null` - нет credential
3. ❌ Системный промпт не инструктирует использовать tools

**Решение:**

```bash
# 1. Проверьте статус
GET /agents/{agent_id}/sqns/status

# 2. Включите SQNS
POST /agents/{agent_id}/sqns/enable-by-password

# 3. Обновите системный промпт
PUT /agents/{agent_id}
{
  "system_prompt": "Используй SQNS инструменты для получения данных..."
}
```

### Проблема: История не сохраняется

**Причины:**

1. ❌ Разные `session_id` для каждого запроса
2. ❌ `max_history_messages=0`

**Решение:**

```bash
# Используйте постоянный session_id для диалога
POST /runs
{
  "agent_id": "...",
  "session_id": "my-chat-session-123",  # ← Одинаковый для всего диалога
  "input_message": "..."
}

# Увеличьте лимит истории
PUT /agents/{agent_id}
{
  "max_history_messages": 20
}
```

### Проблема: Системный промпт не обновляется

**Причина:**

- Старая версия кода не фильтровала system prompts

**Решение:**

- ✅ Код уже исправлен (строки 409-429 в runtime.py)
- Перезапустите контейнер: `docker compose restart api`

---

## Итого

### ✅ Что работает правильно:

1. **SQNS привязка** - каждый агент имеет свой SQNS credential
2. **Системный промпт** - передается и актуализируется при каждом запросе
3. **История сообщений** - сохраняется и передается с фильтрацией старых промптов
4. **Изоляция** - разные агенты используют разные SQNS интеграции
5. **Контекст** - история позволяет вести связный диалог

### 📚 Дополнительные ресурсы:

- [SQNS Tools Reference](./sqns-tools-reference.md) - справочник инструментов
- [SQNS Tools Improvements](./sqns-tools-improvements.md) - улучшения описаний
- [SQNS Frontend Spec](./sqns-frontend-spec.md) - спецификация для фронтенда

---

**Дата:** 26 января 2026  
**Версия:** 1.0
