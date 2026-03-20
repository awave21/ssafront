# API Changes: HTTP Tools Enhancement

## Для Frontend разработчиков

Этот документ описывает новые возможности API для работы с HTTP tools. Вы можете начать интеграцию сразу, UI создавать постепенно.

---

## 🆕 Новые поля в Tool

### Существующие endpoints (`GET/POST/PUT /tools`)

К существующим полям добавлены 3 новых:

```typescript
interface Tool {
  // ... существующие поля ...
  id: string;
  name: string;
  description: string;
  endpoint: string | null;
  execution_type: 'http_webhook' | 'internal';
  auth_type: 'none' | 'api_key' | 'bearer_token' | 'basic_auth' | 'custom_header' | 'query_param' | 'oauth2' | 'service';
  input_schema: JSONSchema;
  status: 'active' | 'deprecated';
  version: number;
  
  // ✨ НОВЫЕ ПОЛЯ:
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';  // default: 'POST'
  parameter_mapping: ParameterMapping | null;                 // default: null
  response_transform: ResponseTransform | null;               // default: null
}
```

### Типы новых полей

```typescript
// Маппинг параметров: куда идёт каждый параметр
type ParameterMapping = Record<string, 'path' | 'query' | 'body' | 'header'>;

// Пример:
{
  "user_id": "path",      // подставится в URL: /users/{user_id}
  "status": "query",      // добавится в URL: ?status=active
  "data": "body"          // пойдёт в тело запроса
}

// Фильтрация ответа
type ResponseTransform = 
  | FieldsTransform
  | JMESPathTransform;

// Режим 1: Визуальный выбор полей
interface FieldsTransform {
  mode: 'fields';
  fields?: Array<{
    source: string;   // путь в исходном JSON: "data.name"
    target: string;   // имя в результате: "user_name"
  }>;
  arrays?: Array<{
    source: string;   // путь к массиву: "data.orders"
    target: string;   // имя в результате: "orders"
    fields: Array<{
      source: string; // путь внутри элемента: "id"
      target: string; // имя в результате: "order_id"
    }>;
  }>;
}

// Режим 2: JMESPath выражение
interface JMESPathTransform {
  mode: 'jmespath';
  expression: string;  // JMESPath выражение
}
```

---

## 🆕 Новые API Endpoints

### 1. Тестовый вызов tool (inline) - `POST /tools/test`

**Назначение**: Протестировать tool ДО сохранения в БД. Для конструктора tool.

**Request**:
```typescript
interface ToolTestRequest {
  // Параметры для вызова
  args: Record<string, any>;
  
  // Конфигурация tool (для тестирования до сохранения):
  endpoint?: string;
  http_method?: string;           // default: 'POST'
  input_schema?: JSONSchema;
  auth_type?: string;             // default: 'none'
  credential_id?: string | null;
  custom_headers?: Record<string, string> | null;
  response_transform?: ResponseTransform | null;
  parameter_mapping?: ParameterMapping | null;
}
```

**Response**:
```typescript
interface ToolTestResponse {
  status_code: number;            // HTTP статус ответа
  latency_ms: number;             // Время выполнения в мс
  response_headers: Record<string, string>;
  raw_body: any;                  // Полный ответ от API
  transformed_body: any | null;   // Отфильтрованный ответ (если был response_transform)
  raw_size_bytes: number;         // Размер оригинального ответа
  transformed_size_bytes: number | null;  // Размер после фильтрации
  error: string | null;           // Ошибка, если была
  request_url: string;            // Итоговый URL (с подставленными path params)
  request_method: string;         // HTTP метод
}
```

**Пример запроса**:
```bash
POST /tools/test
{
  "endpoint": "https://api.github.com/users/{username}",
  "http_method": "GET",
  "args": {
    "username": "torvalds"
  },
  "parameter_mapping": {
    "username": "path"
  },
  "auth_type": "none",
  "response_transform": {
    "mode": "fields",
    "fields": [
      {"source": "login", "target": "username"},
      {"source": "name", "target": "full_name"},
      {"source": "public_repos", "target": "repos_count"}
    ]
  }
}
```

**Пример ответа**:
```json
{
  "status_code": 200,
  "latency_ms": 142,
  "response_headers": {"content-type": "application/json"},
  "raw_body": {
    "login": "torvalds",
    "name": "Linus Torvalds",
    "id": 1024025,
    "public_repos": 6,
    "followers": 200000,
    "...": "еще 50+ полей"
  },
  "transformed_body": {
    "username": "torvalds",
    "full_name": "Linus Torvalds",
    "repos_count": 6
  },
  "raw_size_bytes": 2500,
  "transformed_size_bytes": 180,
  "error": null,
  "request_url": "https://api.github.com/users/torvalds",
  "request_method": "GET"
}
```

**Для UI**: Покажите `raw_body` в Tree/Raw режимах, `transformed_body` в превью, подсчитайте экономию: `(1 - transformed_size / raw_size) * 100%`.

---

### 2. Тестовый вызов сохранённого tool - `POST /tools/{tool_id}/test`

**Назначение**: Протестировать уже сохранённый tool с другими параметрами.

**Request**:
```typescript
interface ToolTestRequest {
  args: Record<string, any>;      // Обязательное - параметры для вызова
  
  // Опциональные (переопределяют настройки tool):
  credential_id?: string | null;
  custom_headers?: Record<string, string> | null;
  response_transform?: ResponseTransform | null;  // можно протестировать другой фильтр
  parameter_mapping?: ParameterMapping | null;
}
```

**Response**: Тот же `ToolTestResponse`.

**Пример**:
```bash
POST /tools/abc-123-def/test
{
  "args": {
    "username": "torvalds"
  }
}
```

---

## 📝 Обновлённые endpoints

### `GET /agents/{agent_id}/tools/details` ✨ НОВЫЙ

Получить все tools привязанные к агенту с полной информацией.

**Response**:
```typescript
interface BindingWithTool {
  // Информация о привязке:
  id: string;
  agent_id: string;
  tool_id: string;
  permission_scope: 'read' | 'write';
  timeout_ms: number | null;
  allowed_domains: string[] | null;
  credential_id: string | null;
  
  // ✨ ПОЛНАЯ информация о tool:
  tool: Tool | null;  // включает http_method, parameter_mapping, response_transform
}
```

**Пример**:
```bash
GET /agents/abc-123/tools/details

# Ответ:
[
  {
    "id": "binding-uuid",
    "agent_id": "abc-123",
    "tool_id": "tool-uuid",
    "permission_scope": "read",
    "timeout_ms": 30000,
    "tool": {
      "id": "tool-uuid",
      "name": "get_github_user",
      "endpoint": "https://api.github.com/users/{username}",
      "http_method": "GET",
      "parameter_mapping": {"username": "path"},
      "response_transform": {...},
      "input_schema": {...}
    }
  }
]
```

**Для UI**: Используйте этот endpoint вместо `/agents/{agent_id}/tools` + `/tools/{tool_id}` для каждого - экономия N+1 запросов!

---

### `POST /tools` и `PUT /tools/{tool_id}`

Теперь принимают новые поля. Все они опциональные (есть дефолты):

```bash
POST /tools
{
  "name": "get_user",
  "description": "Get user from API",
  "endpoint": "https://api.example.com/users/{user_id}",
  "http_method": "GET",                    # ✨ НОВОЕ, default: "POST"
  "execution_type": "http_webhook",
  "auth_type": "bearer_token",
  "input_schema": {
    "type": "object",
    "properties": {
      "user_id": {"type": "string", "description": "User ID"}
    },
    "required": ["user_id"]
  },
  "parameter_mapping": {                   # ✨ НОВОЕ, default: null
    "user_id": "path"
  },
  "response_transform": {                  # ✨ НОВОЕ, default: null
    "mode": "fields",
    "fields": [
      {"source": "data.name", "target": "name"},
      {"source": "data.email", "target": "email"}
    ]
  }
}
```

---

## 🎨 Как строить UI (пошагово)

### Шаг 1: Конструктор параметров

В форме создания tool добавьте:

```tsx
// Выбор HTTP метода
<Select value={httpMethod} onChange={setHttpMethod}>
  <option value="GET">GET</option>
  <option value="POST">POST</option>
  <option value="PUT">PUT</option>
  <option value="PATCH">PATCH</option>
  <option value="DELETE">DELETE</option>
</Select>

// URL с подсказкой о plейсхолдерах
<Input 
  value={endpoint}
  onChange={setEndpoint}
  placeholder="https://api.example.com/users/{user_id}"
  hint="Используйте {param_name} для path параметров"
/>

// Для каждого параметра - выбор расположения
{parameters.map(param => (
  <div key={param.name}>
    <label>{param.name}</label>
    <Select value={param.location} onChange={...}>
      <option value="path">Path (в URL)</option>
      <option value="query">Query (?param=value)</option>
      <option value="body">Body (JSON)</option>
    </Select>
  </div>
))}
```

**Логика**:
1. Парсите URL на наличие `{param_name}`
2. Автоматически создавайте параметр с `location: "path"`
3. Генерируйте `parameter_mapping` из выбранных location

### Шаг 2: Кнопка "Тестировать"

```tsx
const handleTest = async () => {
  const response = await fetch('/tools/test', {
    method: 'POST',
    body: JSON.stringify({
      endpoint,
      http_method: httpMethod,
      args: testArgs,  // заполненные пользователем значения
      parameter_mapping: parameterMapping,
      auth_type: authType,
      credential_id: credentialId
    })
  });
  
  const result = await response.json();
  
  // Показать результат
  setTestResult(result);
  setRawBody(result.raw_body);
  setTransformedBody(result.transformed_body);
  
  // Подсчитать экономию
  const savings = result.transformed_size_bytes 
    ? Math.round((1 - result.transformed_size_bytes / result.raw_size_bytes) * 100)
    : 0;
  setSavingsPercent(savings);
};
```

### Шаг 3: Визуализация ответа (Tree/Raw)

```tsx
// Tree режим
<JsonTree data={rawBody} />

// Raw режим
<CodeEditor value={JSON.stringify(rawBody, null, 2)} readOnly />

// Переключатель
<SegmentedControl value={viewMode} onChange={setViewMode}>
  <option value="tree">Tree</option>
  <option value="raw">Raw</option>
</SegmentedControl>
```

### Шаг 4: Конструктор фильтра

После тестового вызова, если `raw_body` не null:

```tsx
const buildFieldTree = (obj: any, prefix = ''): Field[] => {
  if (!obj || typeof obj !== 'object') return [];
  
  if (Array.isArray(obj)) {
    if (obj.length === 0) return [];
    // Берём первый элемент как образец
    return buildFieldTree(obj[0], `${prefix}[]`);
  }
  
  return Object.entries(obj).map(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return {
      path,
      key,
      type: Array.isArray(value) ? 'array' : typeof value,
      example: typeof value === 'object' ? undefined : value,
      selected: true,  // по умолчанию все выбраны
      rename: key,
      children: typeof value === 'object' ? buildFieldTree(value, path) : undefined
    };
  });
};

// UI
const fields = buildFieldTree(rawBody);

{fields.map(field => (
  <Checkbox 
    key={field.path}
    checked={field.selected}
    onChange={(checked) => updateField(field.path, checked)}
  >
    {field.path} → 
    <Input value={field.rename} onChange={...} />
  </Checkbox>
))}

// Live preview фильтрованного ответа
const previewFiltered = () => {
  const selectedFields = fields.filter(f => f.selected);
  const transform = {
    mode: 'fields',
    fields: selectedFields.map(f => ({
      source: f.path,
      target: f.rename
    }))
  };
  
  // Применить локально
  return applyTransform(rawBody, transform);
};
```

### Шаг 5: Показатель экономии

```tsx
<div className="savings-badge">
  <span>Было: {rawSizeBytes} bytes</span>
  <span>Стало: {transformedSizeBytes} bytes</span>
  <span className="percentage">−{savingsPercent}% токенов</span>
</div>
```

---

## 🔧 Вспомогательные функции для фронтенда

### Парсинг URL и автосоздание path параметров

```typescript
function extractPathParams(url: string): string[] {
  const regex = /\{([^}]+)\}/g;
  const matches = [...url.matchAll(regex)];
  return matches.map(m => m[1]);
}

// Пример:
extractPathParams('https://api.com/users/{user_id}/orders/{order_id}')
// → ['user_id', 'order_id']
```

### Генерация parameter_mapping

```typescript
function generateParameterMapping(
  parameters: Parameter[]
): Record<string, string> {
  const mapping: Record<string, string> = {};
  parameters.forEach(param => {
    mapping[param.name] = param.location; // 'path' | 'query' | 'body'
  });
  return mapping;
}
```

### Генерация response_transform из выбранных полей

```typescript
function generateFieldsTransform(
  selectedFields: Field[]
): ResponseTransform {
  // Разделить на обычные поля и массивы
  const fields = selectedFields.filter(f => !f.path.includes('[]'));
  const arrayFields = selectedFields.filter(f => f.path.includes('[]'));
  
  const transform: FieldsTransform = {
    mode: 'fields',
    fields: fields.map(f => ({
      source: f.path,
      target: f.rename
    }))
  };
  
  // Группировать поля массивов
  const arrays = groupBy(arrayFields, f => f.path.split('[]')[0]);
  transform.arrays = Object.entries(arrays).map(([source, fields]) => ({
    source,
    target: source.split('.').pop() || 'items',
    fields: fields.map(f => ({
      source: f.path.split('[]')[1].slice(1), // убрать начальную точку
      target: f.rename
    }))
  }));
  
  return transform;
}
```

### Применение фильтра локально (для preview)

```typescript
function applyFieldsTransform(data: any, transform: FieldsTransform): any {
  const result: any = {};
  
  // Обычные поля
  transform.fields?.forEach(({ source, target }) => {
    result[target] = resolvePath(data, source);
  });
  
  // Массивы
  transform.arrays?.forEach(({ source, target, fields }) => {
    const sourceArray = resolvePath(data, source);
    if (!Array.isArray(sourceArray)) return;
    
    result[target] = sourceArray.map(item => {
      const newItem: any = {};
      fields.forEach(({ source: s, target: t }) => {
        newItem[t] = resolvePath(item, s);
      });
      return newItem;
    });
  });
  
  return result;
}

function resolvePath(obj: any, path: string): any {
  return path.split('.').reduce((current, key) => 
    current?.[key], obj
  );
}
```

---

## 📦 TypeScript типы (полный набор)

```typescript
// Скопируйте в ваш frontend проект

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
export type ParameterLocation = 'path' | 'query' | 'body' | 'header';
export type AuthType = 'none' | 'api_key' | 'bearer_token' | 'basic_auth' | 'custom_header' | 'query_param' | 'oauth2' | 'service';

export interface Tool {
  id: string;
  tenant_id: string;
  name: string;
  description: string;
  endpoint: string | null;
  http_method: HttpMethod;
  execution_type: 'http_webhook' | 'internal';
  auth_type: AuthType;
  input_schema: Record<string, any>;
  parameter_mapping: Record<string, ParameterLocation> | null;
  response_transform: ResponseTransform | null;
  status: 'active' | 'deprecated';
  version: number;
  created_at: string;
  updated_at: string | null;
}

export interface ResponseTransform {
  mode: 'fields' | 'jmespath';
  fields?: Array<{ source: string; target: string }>;
  arrays?: Array<{
    source: string;
    target: string;
    fields: Array<{ source: string; target: string }>;
  }>;
  expression?: string;  // для jmespath режима
}

export interface ToolTestRequest {
  args: Record<string, any>;
  endpoint?: string;
  http_method?: string;
  input_schema?: Record<string, any>;
  auth_type?: string;
  credential_id?: string | null;
  custom_headers?: Record<string, string> | null;
  response_transform?: ResponseTransform | null;
  parameter_mapping?: Record<string, ParameterLocation> | null;
}

export interface ToolTestResponse {
  status_code: number;
  latency_ms: number;
  response_headers: Record<string, string>;
  raw_body: any;
  transformed_body: any | null;
  raw_size_bytes: number;
  transformed_size_bytes: number | null;
  error: string | null;
  request_url: string;
  request_method: string;
}
```

---

## 🚦 Проверить готовность backend

```bash
# 1. Проверить, что новые поля доступны
curl http://localhost:8000/tools | jq '.[0] | keys' 
# Должны быть: http_method, parameter_mapping, response_transform

# 2. Проверить новый endpoint
curl -X POST http://localhost:8000/tools/test \
  -H "Content-Type: application/json" \
  -d '{"endpoint": "https://api.github.com/users/torvalds", "http_method": "GET", "args": {}}'
# Должен вернуть ToolTestResponse

# 3. Проверить миграцию
docker exec agentsapp-db-1 psql -U postgres -d agentsapp -c "\d tools" | grep http_method
# Должна быть колонка http_method
```

---

## ✅ Чеклист для фронтенда

- [ ] Обновить типы Tool (добавить 3 новых поля)
- [ ] Добавить выбор HTTP метода в форму
- [ ] Добавить маппинг параметров (path/query/body чекбоксы)
- [ ] Реализовать `POST /tools/test` для кнопки "Тестировать"
- [ ] Показывать raw_body в Tree/Raw режимах
- [ ] Построить дерево полей из raw_body
- [ ] Реализовать выбор полей чекбоксами
- [ ] Live preview фильтрованного ответа
- [ ] Показывать экономию токенов (%)
- [ ] Сохранять response_transform при создании tool

---

## 💡 Минимальная реализация (MVP)

Если нужно быстро:

1. **Только GET/POST** методы (остальные позже)
2. **Только Fields режим** фильтрации (JMESPath позже)
3. **Без вложенных массивов** (только простые поля)
4. **Базовый preview** (без Tree, только Raw JSON)

Это даст 80% пользы с 20% усилий.

---

## 📞 Контакты

Если что-то непонятно или нужна помощь:
- Backend готов и протестирован
- Все примеры рабочие
- Можете начинать интеграцию прямо сейчас

Успехов! 🚀
