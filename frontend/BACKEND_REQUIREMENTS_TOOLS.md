# Backend API для работы с Tools - Используемые Endpoints

## Архитектура

Tools хранятся **глобально на уровне tenant** и **привязываются к агентам** через bindings. Это позволяет переиспользовать одну функцию между разными агентами.

```
Tenant
  └─ Tools (глобальные)
       ├─ get_user_data
       ├─ create_appointment
       └─ send_email
  └─ Agents
       ├─ Support Bot
       │    └─ Bindings → [get_user_data, create_appointment]
       └─ Sales Bot
            └─ Bindings → [get_user_data, send_email]
```

---

## API Endpoints (Используемые Frontend)

### 1. Загрузить функции агента (с полными данными)

**GET** `/agents/{agent_id}/tools/details` ⭐ **ИСПОЛЬЗУЕТСЯ**

Возвращает bindings с полной информацией о tools в одном запросе (N+1 solution).

**Response:**
```typescript
BindingWithTool[] = [
  {
    id: "binding_123",
    agent_id: "agent_456",
    tool_id: "tool_789",
    permission_scope: "write",
    credential_id: null,
    tool: {
      id: "tool_789",
      name: "get_user_data",
      description: "...",
      endpoint: "https://api.example.com/users/{user_id}",
      http_method: "GET",
      parameter_mapping: {...},
      response_transform: {...},
      // ... все остальные поля
    }
  }
]
```

### 2. Создать новый tool (глобально для tenant)

**POST** `/tools` ⭐ **ИСПОЛЬЗУЕТСЯ**

**Request Body:**
```json
{
  "name": "get_user_data",
  "description": "Получение данных пользователя",
  "endpoint": "https://api.example.com/users/{user_id}",
  "http_method": "GET",
  "execution_type": "http_webhook",
  "auth_type": "none",
  "input_schema": {
    "type": "object",
    "properties": {
      "user_id": { "type": "string" }
    }
  },
  "parameter_mapping": {
    "user_id": "path"
  },
  "response_transform": null
}
```

### 3. Привязать tool к агенту

**POST** `/agents/{agent_id}/tools/{tool_id}` ⭐ **ИСПОЛЬЗУЕТСЯ**

**Request Body:**
```json
{
  "permission_scope": "write",
  "credential_id": null
}
```

**Response 201:**
```json
{
  "id": "tool_123",
  "tenant_id": "tenant_456",
  "name": "get_user_data",
  "description": "Получение данных пользователя",
  "endpoint": "https://api.example.com/users/{user_id}",
  "http_method": "GET",
  "execution_type": "http_webhook",
  "auth_type": "none",
  "input_schema": {
    "type": "object",
    "properties": {
      "user_id": { "type": "string" }
    }
  },
  "parameter_mapping": {
    "user_id": "path"
  },
  "response_transform": null,
  "status": "active",
  "version": 1,
  "created_at": "2026-02-10T...",
  "is_deleted": false
}
```

**⚠️ ВАЖНО:** Backend ОБЯЗАТЕЛЬНО должен вернуть полный объект Tool со всеми полями, включая сгенерированный `id`.

---

### 4. Обновить tool

**PUT** `/tools/{tool_id}` ⭐ **ИСПОЛЬЗУЕТСЯ**

**Request Body:** (те же поля что и при создании)

**Response 200:** (полный обновлённый объект Tool)

---

### 5. Отвязать tool от агента

**DELETE** `/agents/{agent_id}/tools/{tool_id}` ⭐ **ИСПОЛЬЗУЕТСЯ**

Удаляет binding между агентом и tool. Сам tool остаётся в системе.

**Response 204:** No Content

---

### 5. Тестировать функцию (УЖЕ РЕАЛИЗОВАНО в вашем гайде)

**POST** `/tools/test`

Этот endpoint уже описан в вашем гайде и работает согласно спецификации.

---

## Структура данных Tool

```typescript
interface Tool {
  id?: string;                    // ID (генерируется на бэкенде)
  name: string;                   // Название функции
  description: string;            // Описание
  endpoint: string;               // URL endpoint
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  execution_type: string;         // 'http' или 'local'
  auth_type: string;              // 'none', 'bearer', 'basic', 'api_key', 'oauth2'
  credential_id?: string | null;  // ID креденшалов (если используется)
  input_schema: any;              // JSON Schema для валидации входных параметров
  parameter_mapping: Record<string, 'path' | 'query' | 'body'> | null;
  response_transform: ResponseTransform | null;
  is_active?: boolean;            // Активна ли функция
}

interface ResponseTransform {
  mode: 'fields' | 'jmespath';
  fields?: Array<{source: string; target: string}>;
  arrays?: Array<{
    source: string;
    target: string;
    fields: Array<{source: string; target: string}>;
  }>;
  expression?: string;  // Для JMESPath режима
}
```

---

## Что УЖЕ работает на Frontend

✅ **Загрузка функций агента** - `GET /agents/{agent_id}/tools/details`  
✅ **Создание функций** - двухшаговый процесс:
   1. `POST /tools` - создание tool
   2. `POST /agents/{agent_id}/tools/{tool_id}` - привязка к агенту  
✅ **Редактирование** - все поля редактируются, `PUT /tools/{tool_id}`  
✅ **Удаление** - `DELETE /agents/{agent_id}/tools/{tool_id}` (отвязка от агента)  
✅ **Добавление параметров** - таблица параметров с типами  
✅ **Генерация Input Schema** - автоматически из параметров  
✅ **Тестирование** - кнопка "Run Request" вызывает `POST /tools/test`  
✅ **Response Transform** - визуальный выбор полей из ответа  
✅ **Live Preview** - показ отфильтрованного ответа  
✅ **Fields ↔ JSON** - переключение между режимами  
✅ **Автосохранение schema** - при изменении параметров  

---

## Что УЖЕ реализовано на Backend (согласно вашей документации)

✅ **GET /tools** - список всех tools tenant  
✅ **POST /tools** - создание tool  
✅ **PUT /tools/{tool_id}** - обновление tool  
✅ **DELETE /tools/{tool_id}** - soft delete tool  
✅ **POST /tools/test** - тестирование без сохранения  
✅ **POST /tools/{tool_id}/test** - тестирование сохранённого  
✅ **GET /agents/{agent_id}/tools/details** - bindings с full tool data  
✅ **POST /agents/{agent_id}/tools/{tool_id}** - привязка к агенту  
✅ **DELETE /agents/{agent_id}/tools/{tool_id}** - отвязка от агента  

**Вывод:** Backend полностью готов! ✨

---

## Примеры запросов

### Полный пример создания и привязки

```bash
# Шаг 1: Создать tool
TOOL_ID=$(curl -X POST http://localhost:8000/tools \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_weather",
    "description": "Получить погоду по городу",
    "endpoint": "https://api.weather.com/current/{city}",
    "http_method": "GET",
    "execution_type": "http_webhook",
    "auth_type": "none",
    "input_schema": {
      "type": "object",
      "properties": {
        "city": { "type": "string" }
      },
      "required": ["city"]
    },
    "parameter_mapping": {
      "city": "path"
    },
    "response_transform": null
  }' | jq -r '.id')

# Шаг 2: Привязать к агенту
curl -X POST http://localhost:8000/agents/agent_123/tools/$TOOL_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "permission_scope": "write",
    "credential_id": null
  }'
```

---

## База данных

Предлагаемая структура таблицы `tools`:

```sql
CREATE TABLE tools (
  id VARCHAR(255) PRIMARY KEY,
  tenant_id VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT,
  endpoint TEXT NOT NULL,
  http_method VARCHAR(10) NOT NULL,
  execution_type VARCHAR(50) NOT NULL DEFAULT 'http',
  auth_type VARCHAR(50) NOT NULL DEFAULT 'none',
  credential_id VARCHAR(255),
  input_schema JSON,
  parameter_mapping JSON,
  response_transform JSON,
  is_active BOOLEAN DEFAULT true,
  is_deleted BOOLEAN DEFAULT false,
  version INTEGER DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (credential_id) REFERENCES credentials(id) ON DELETE SET NULL
);

CREATE INDEX idx_tools_tenant_id ON tools(tenant_id);
CREATE INDEX idx_tools_is_active ON tools(is_active);
CREATE INDEX idx_tools_is_deleted ON tools(is_deleted);
```

**Note:** Tools привязаны к `tenant_id`, а не к `agent_id`. Это позволяет переиспользовать функции между разными агентами одного tenant.

---

## Flow создания новой функции

Frontend выполняет **два последовательных запроса**:

```typescript
// Шаг 1: Создать tool глобально для tenant
const tool = await POST('/tools', {
  name: "get_weather",
  endpoint: "https://api.weather.com/current/{city}",
  http_method: "GET",
  parameter_mapping: { city: "path" },
  // ...
})
// Response: { id: "tool_789", ... }

// Шаг 2: Привязать к агенту
await POST(`/agents/${agentId}/tools/${tool.id}`, {
  permission_scope: "write",
  credential_id: null
})
```

**Почему два запроса?**
- Tool создаётся глобально → можно переиспользовать между агентами
- Binding привязывает tool к конкретному агенту

## Flow удаления функции

Frontend отвязывает tool от агента (НЕ удаляет сам tool):

```typescript
// Отвязать от агента
await DELETE(`/agents/${agentId}/tools/${toolId}`)

// Tool остаётся в системе и может использоваться другими агентами
```

**Чтобы полностью удалить tool** (если нужно):
```typescript
await DELETE(`/tools/${toolId}`)  // Soft delete (is_deleted = true)
```

---

## Frontend Implementation Summary

### Компоненты:
- `components/agents/AgentFunctionsPanel.vue` - основной редактор
- `components/agents/FieldNode.vue` - дерево полей для response transform
- `types/tool.ts` - TypeScript типы

### Используемые endpoints:
1. **При загрузке страницы:** `GET /agents/{agent_id}/tools/details`
2. **При создании:** `POST /tools` → `POST /agents/{agent_id}/tools/{tool_id}`
3. **При обновлении:** `PUT /tools/{tool_id}`
4. **При удалении:** `DELETE /agents/{agent_id}/tools/{tool_id}`
5. **При тестировании:** `POST /tools/test`

### Особенности реализации:
- ✅ Автоматическая генерация `input_schema` из параметров
- ✅ Синхронизация Fields ↔ JSON при переключении режимов
- ✅ Live preview отфильтрованного ответа
- ✅ Визуальная индикация несохранённых изменений
- ✅ Реактивное обновление списка через `splice()`

## 🎉 Готово к использованию!

Backend и Frontend полностью интегрированы. Все endpoints реализованы согласно вашей спецификации.
