# SQNS Quick Check - Быстрая проверка интеграции

## ✅ Чеклист проверки SQNS интеграции

### 1. Проверка подключения к агенту

```bash
curl -X GET "https://agentsapp.integration-ai.ru/agents/{agent_id}" \
  -H "Authorization: Bearer TOKEN"
```

**Ожидается:**
```json
{
  "id": "dc7a2d54-983c-4143-be9b-3082242c207b",
  "sqns_enabled": true,        ✅ должен быть true
  "sqns_configured": true,     ✅ должен быть true
  "sqns_host": "crm...",       ✅ не должен быть null
  "sqns_credential_id": "...", ✅ не должен быть null
  "sqns_status": "ok",         ✅ должен быть "ok"
  "system_prompt": "..."       ✅ должен содержать инструкции про SQNS
}
```

---

### 2. Проверка системного промпта

**Хороший промпт содержит:**

```
✅ "Ты — ассистент ... с доступом к SQNS CRM"
✅ "Когда пользователь спрашивает про специалистов → вызови sqns_list_resources()"
✅ "ВСЕГДА используй инструменты для получения данных"
✅ "НИКОГДА не придумывай информацию"
```

**Плохой промпт:**

```
❌ "Ты — ассистент клиники" (без упоминания SQNS)
❌ Нет инструкций, когда использовать инструменты
```

**Обновить промпт:**

```bash
curl -X PUT "https://agentsapp.integration-ai.ru/agents/{agent_id}" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "Ты — ассистент медицинской клиники с доступом к SQNS CRM.\n\nИНСТРУКЦИИ:\n- Когда спрашивают про специалистов → вызови sqns_list_resources()\n- Когда спрашивают про услуги → вызови sqns_list_services()\n- Всегда используй инструменты, не придумывай информацию!"
  }'
```

---

### 3. Проверка истории сообщений

```bash
# Запрос 1: создаем session
curl -X POST "https://agentsapp.integration-ai.ru/runs" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "{agent_id}",
    "session_id": "test-session-123",
    "input_message": "Какие специалисты работают?"
  }'

# Запрос 2: используем тот же session_id
curl -X POST "https://agentsapp.integration-ai.ru/runs" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "{agent_id}",
    "session_id": "test-session-123",
    "input_message": "Запишите меня к Иванову"
  }'
```

**Ожидается:**
- ✅ Второй запрос знает, кто такой "Иванов" (из первого запроса)
- ✅ Не спрашивает повторно "К какому специалисту?"

---

### 4. Проверка работы инструментов

**Тест 1: Список специалистов**

```bash
curl -X POST "https://agentsapp.integration-ai.ru/runs" \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "{agent_id}",
    "input_message": "Какие специалисты у вас работают?"
  }'
```

**Ожидается:**
```json
{
  "status": "succeeded",
  "output_message": "У нас работают:\n1. Иванов Иван - Стоматолог\n2. Петрова Анна - Ортодонт",
  "messages": [
    {
      "kind": "request",
      "parts": [
        {"part_kind": "user-prompt", "content": "Какие специалисты..."}
      ]
    },
    {
      "kind": "response",
      "parts": [
        {
          "part_kind": "tool-call",
          "tool_name": "sqns_list_resources"  ✅ инструмент вызван!
        }
      ]
    }
  ]
}
```

**НЕ должно быть:**
```json
❌ "output_message": "У нас работают разные специалисты"  // общий ответ
❌ "messages": [] без "tool-call"  // инструменты не вызваны
```

---

## 🔍 Диагностика проблем

### Проблема: Агент не вызывает SQNS инструменты

**Проверьте:**

```bash
# 1. SQNS включен?
curl -X GET ".../agents/{agent_id}" | jq '.sqns_enabled, .sqns_configured'
# Должно быть: true true

# 2. Credential существует?
curl -X GET ".../agents/{agent_id}" | jq '.sqns_credential_id'
# Не должно быть: null

# 3. Статус OK?
curl -X GET ".../agents/{agent_id}/sqns/status"
# Должно быть: {"status": "ok"}

# 4. Системный промпт упоминает SQNS?
curl -X GET ".../agents/{agent_id}" | jq '.system_prompt'
# Должен содержать: "SQNS", "sqns_list_resources", "инструменты"
```

### Проблема: История не работает

**Проверьте:**

```bash
# 1. Используете ли одинаковый session_id?
# ✅ "session_id": "chat-123"  // одинаковый для диалога
# ❌ "session_id": "chat-1", "chat-2", "chat-3"  // разные

# 2. Лимит истории не слишком маленький?
curl -X GET ".../agents/{agent_id}" | jq '.max_history_messages'
# Должно быть: >= 10

# 3. Смотрите логи
docker compose logs api | grep "message_history_length"
```

---

## 📊 Проверка логов

```bash
# Проверка SQNS подключения
docker compose logs api --tail=100 | grep sqns

# Что искать:
✅ sqns_toolset_prepared - инструменты загружены
✅ sqns_list_resources - инструмент вызван
✅ sqns_mcp_server_created: tool_count=8 - все 8 инструментов

# Проверка системного промпта
docker compose logs api --tail=100 | grep system_prompt

# Что искать:
✅ system_prompt_preview - промпт передан
✅ new_system_prompt_prepended - добавлен в историю

# Проверка истории
docker compose logs api --tail=100 | grep history

# Что искать:
✅ message_history_length=5 - история загружена
✅ removed_system_prompts=1 - старый промпт удален
```

---

## 🎯 Быстрый тест "все работает"

Запустите эту последовательность:

```bash
# 1. Первое сообщение (создаем контекст)
curl -X POST ".../runs" -d '{
  "agent_id": "{id}",
  "session_id": "quick-test",
  "input_message": "Какие специалисты работают?"
}'

# Ожидается:
# ✅ Ответ со списком РЕАЛЬНЫХ специалистов (не общий ответ)
# ✅ В messages есть tool-call "sqns_list_resources"

# 2. Второе сообщение (проверка истории)
curl -X POST ".../runs" -d '{
  "agent_id": "{id}",
  "session_id": "quick-test",
  "input_message": "Запишите меня к первому"
}'

# Ожидается:
# ✅ Агент знает, кто "первый" из предыдущего ответа
# ✅ Вызывает sqns_find_client, sqns_list_slots, sqns_create_visit
# ✅ Не спрашивает "К какому специалисту?"
```

---

## ✅ Чеклист "Все ОК"

- [ ] `sqns_enabled=true` и `sqns_configured=true`
- [ ] `sqns_credential_id` не null
- [ ] `sqns_status="ok"`
- [ ] Системный промпт содержит инструкции про SQNS
- [ ] Агент вызывает SQNS инструменты (есть tool-call в messages)
- [ ] Агент возвращает реальные данные (не общие ответы)
- [ ] История работает (с одним session_id контекст сохраняется)
- [ ] `max_history_messages >= 10`
- [ ] Логи показывают `sqns_toolset_prepared`

Если все пункты ✅ - интеграция работает правильно!

---

## 📚 Дополнительно

- [Полная документация flow](./sqns-integration-flow.md)
- [Справочник инструментов](./sqns-tools-reference.md)
- [Улучшения](./sqns-tools-improvements.md)
