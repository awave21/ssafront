# HTTP Tools - API Endpoints Summary

## 📌 Все endpoints для работы с HTTP Tools

### 1. Управление Tools

#### `GET /tools`
Получить список всех tools (включает новые поля).

**Response**:
```typescript
Tool[] // с http_method, parameter_mapping, response_transform
```

#### `POST /tools`
Создать новый tool.

**Request**:
```typescript
{
  name: string;
  description: string;
  endpoint: string;
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';  // ✨ NEW
  execution_type: 'http_webhook';
  auth_type: string;
  input_schema: JSONSchema;
  parameter_mapping?: Record<string, string>;                // ✨ NEW
  response_transform?: ResponseTransform;                    // ✨ NEW
}
```

#### `PUT /tools/{tool_id}`
Обновить tool.

#### `DELETE /tools/{tool_id}`
Удалить tool (soft delete).

---

### 2. Тестирование Tools (✨ НОВЫЕ)

#### `POST /tools/test`
Протестировать tool БЕЗ сохранения (для конструктора UI).

**Request**:
```typescript
{
  endpoint: string;
  http_method: string;
  args: Record<string, any>;
  parameter_mapping?: Record<string, string>;
  response_transform?: ResponseTransform;
  auth_type?: string;
  credential_id?: string;
}
```

**Response**:
```typescript
{
  status_code: number;
  latency_ms: number;
  raw_body: any;
  transformed_body: any | null;
  raw_size_bytes: number;
  transformed_size_bytes: number | null;
  error: string | null;
  request_url: string;
  request_method: string;
}
```

**Использование**: Кнопка "Тестировать" в UI при создании tool.

#### `POST /tools/{tool_id}/test`
Протестировать сохранённый tool.

**Request**:
```typescript
{
  args: Record<string, any>;  // Обязательное
  // Опционально можно переопределить:
  credential_id?: string;
  response_transform?: ResponseTransform;
}
```

**Response**: Тот же, что у `/tools/test`.

**Использование**: Проверка работы существующего tool с другими параметрами.

---

### 3. Привязка Tools к Агентам

#### `GET /agents/{agent_id}/tools`
Получить bindings (только IDs и настройки привязки).

**Response**:
```typescript
interface Binding {
  id: string;
  agent_id: string;
  tool_id: string;              // только ID!
  permission_scope: 'read' | 'write';
  timeout_ms: number | null;
  allowed_domains: string[] | null;
}[]
```

**Минус**: Нужны дополнительные запросы для получения данных tool.

#### `GET /agents/{agent_id}/tools/details` ✨ НОВЫЙ - ИСПОЛЬЗУЙТЕ ЭТОТ!
Получить bindings С ПОЛНОЙ информацией о tools (N+1 решение).

**Response**:
```typescript
interface BindingWithTool {
  // Настройки привязки:
  id: string;
  agent_id: string;
  tool_id: string;
  permission_scope: 'read' | 'write';
  timeout_ms: number | null;
  allowed_domains: string[] | null;
  credential_id: string | null;
  
  // ✨ ПОЛНАЯ информация о tool в одном запросе:
  tool: {
    id: string;
    name: string;
    description: string;
    endpoint: string;
    http_method: string;             // ✨
    parameter_mapping: {...};        // ✨
    response_transform: {...};       // ✨
    input_schema: {...};
    auth_type: string;
    // ... остальные поля
  } | null;
}[]
```

**Плюс**: Один запрос вместо 1 + N запросов!

**Использование**: 
- Показ списка tools агента в UI
- Редактор агента (список доступных tools)
- Dashboard агента

#### `POST /agents/{agent_id}/tools/{tool_id}`
Привязать tool к агенту.

**Request**:
```typescript
{
  permission_scope?: 'read' | 'write';
  timeout_ms?: number;
  allowed_domains?: string[];
  credential_id?: string;
}
```

#### `DELETE /agents/{agent_id}/tools/{tool_id}`
Отвязать tool от агента.

---

## 🎯 Рекомендованный flow для UI

### Создание нового HTTP Tool

```
1. Пользователь заполняет форму:
   - Название, описание
   - HTTP метод (dropdown: GET/POST/PUT/PATCH/DELETE)
   - URL endpoint с {placeholders}
   - Параметры (автоопределение из URL + ручное добавление)
   - Для каждого параметра: path/query/body

2. Кнопка "Тестировать":
   POST /tools/test
   {
     endpoint: "https://api.github.com/users/{username}",
     http_method: "GET",
     args: {username: "torvalds"},
     parameter_mapping: {username: "path"}
   }

3. Показать результат:
   - Status: 200 OK ✓
   - Latency: 142ms
   - Response: [Tree/Raw view]
   
4. Построить дерево полей из raw_body:
   - Чекбоксы для выбора полей
   - Live preview отфильтрованного ответа
   - Показать экономию: "−93% токенов 🎉"

5. Сохранить:
   POST /tools
   {
     ...,
     http_method: "GET",
     parameter_mapping: {...},
     response_transform: {...}  // из выбранных чекбоксов
   }
```

### Просмотр tools агента

```
1. Открыть страницу агента

2. Загрузить tools одним запросом:
   GET /agents/{agent_id}/tools/details
   
3. Показать таблицу:
   ┌────────────────┬─────────┬──────────────────────────┬─────────┐
   │ Tool Name      │ Method  │ Endpoint                 │ Status  │
   ├────────────────┼─────────┼──────────────────────────┼─────────┤
   │ get_user       │ GET     │ api.github.com/users/... │ Active  │
   │ create_issue   │ POST    │ api.github.com/repos/... │ Active  │
   │ update_status  │ PATCH   │ api.example.com/...      │ Active  │
   └────────────────┴─────────┴──────────────────────────┴─────────┘
   
4. При клике - показать детали:
   - Полная конфигурация tool
   - Кнопка "Тестировать" → POST /tools/{tool_id}/test
   - Кнопка "Отвязать" → DELETE /agents/{agent_id}/tools/{tool_id}
```

---

## 📊 Сравнение endpoints

### Старый подход (N+1 проблема):
```typescript
// 1 запрос
const bindings = await fetch(`/agents/${agentId}/tools`);
// bindings = [{tool_id: "abc"}, {tool_id: "def"}, ...]

// N запросов (для каждого tool отдельно!)
const tools = await Promise.all(
  bindings.map(b => fetch(`/tools/${b.tool_id}`))
);
```

**Итого**: 1 + N запросов = медленно 🐌

### Новый подход (один запрос):
```typescript
// 1 запрос, все данные
const bindingsWithTools = await fetch(
  `/agents/${agentId}/tools/details`
);
// bindingsWithTools = [
//   {tool_id: "abc", tool: {...полные данные...}},
//   {tool_id: "def", tool: {...полные данные...}},
// ]
```

**Итого**: 1 запрос = быстро 🚀

---

## ✅ Checklist для фронтенда

### Phase 1 (MVP)
- [ ] Обновить типы Tool (добавить 3 поля)
- [ ] Добавить выбор HTTP метода в форму
- [ ] Кнопка "Тестировать" → `POST /tools/test`
- [ ] Показ результата теста (raw_body, status, latency)
- [ ] Сохранение новых полей при создании tool

### Phase 2 (Фильтр ответов)
- [ ] Построить дерево полей из raw_body
- [ ] Чекбоксы выбора полей
- [ ] Live preview отфильтрованного ответа
- [ ] Показать экономию токенов (%)
- [ ] Сохранение response_transform

### Phase 3 (Просмотр tools агента)
- [ ] Использовать `/agents/{agent_id}/tools/details`
- [ ] Показ списка tools агента с полной инфой
- [ ] Тестирование tool из карточки агента

---

## 🔗 Дополнительная документация

- **API_CHANGES_HTTP_TOOLS.md** - Полная документация с TypeScript типами
- **TESTING_GUIDE.md** - curl примеры
- **http_tools_api.postman_collection.json** - Postman коллекция
- **example_http_tool.json** - Примеры конфигураций

---

## 💡 TL;DR для фронтенда

**Три главных endpoint:**

1. `POST /tools/test` - тестировать tool перед сохранением
2. `POST /tools` - сохранить tool (с http_method, parameter_mapping, response_transform)
3. `GET /agents/{agent_id}/tools/details` - получить все tools агента одним запросом ⭐

Начните с них!
