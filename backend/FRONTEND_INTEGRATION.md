# HTTP Tools - Frontend Integration Guide

## 🎯 Что нужно сделать на фронте

Backend готов и ждёт. Вот конкретные задачи для фронтенд-команды с приоритетами.

---

## 📋 Phase 1: Минимальная интеграция (2-3 часа)

Базовая поддержка новых полей без визуального конструктора.

### Task 1.1: Обновить типы (10 минут)

**Файл**: `types/tool.ts` (или где у вас типы)

```typescript
// Добавить 3 новых поля
export interface Tool {
  // ... существующие поля
  http_method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  parameter_mapping: Record<string, 'path' | 'query' | 'body'> | null;
  response_transform: ResponseTransform | null;
}

export interface ResponseTransform {
  mode: 'fields' | 'jmespath';
  fields?: Array<{source: string; target: string}>;
  arrays?: Array<{
    source: string;
    target: string;
    fields: Array<{source: string; target: string}>;
  }>;
  expression?: string;
}

export interface ToolTestRequest {
  args: Record<string, any>;
  endpoint?: string;
  http_method?: string;
  parameter_mapping?: Record<string, string> | null;
  auth_type?: string;
  credential_id?: string | null;
  response_transform?: ResponseTransform | null;
}

export interface ToolTestResponse {
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

### Task 1.2: Добавить выбор HTTP метода в форму (30 минут)

**Где**: Форма создания/редактирования tool

```vue
<template>
  <FormField label="HTTP Method">
    <Select v-model="tool.http_method">
      <option value="GET">GET</option>
      <option value="POST">POST</option>
      <option value="PUT">PUT</option>
      <option value="PATCH">PATCH</option>
      <option value="DELETE">DELETE</option>
    </Select>
  </FormField>
</template>
```

**Default**: `'POST'` (для обратной совместимости)

### Task 1.3: Кнопка "Тестировать" (1 час)

```vue
<template>
  <Button @click="testTool" :loading="testing">
    🧪 Тестировать
  </Button>
  
  <Modal v-if="testResult" @close="testResult = null">
    <h3>Результат теста</h3>
    
    <div class="status">
      <Badge :color="testResult.status_code === 200 ? 'green' : 'red'">
        {{ testResult.status_code }}
      </Badge>
      <span>{{ testResult.latency_ms }}ms</span>
    </div>
    
    <div class="url">
      {{ testResult.request_method }} {{ testResult.request_url }}
    </div>
    
    <Tabs>
      <Tab label="Raw Response">
        <CodeEditor 
          :value="JSON.stringify(testResult.raw_body, null, 2)" 
          language="json"
          readonly
        />
      </Tab>
      
      <Tab label="Details">
        <pre>{{ testResult }}</pre>
      </Tab>
    </Tabs>
  </Modal>
</template>

<script setup lang="ts">
const testTool = async () => {
  testing.value = true;
  
  try {
    const response = await fetch('/tools/test', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${authToken}`
      },
      body: JSON.stringify({
        endpoint: tool.value.endpoint,
        http_method: tool.value.http_method,
        args: testArgs.value,  // заполняет пользователь
        parameter_mapping: tool.value.parameter_mapping,
        auth_type: tool.value.auth_type,
        credential_id: tool.value.credential_id
      })
    });
    
    testResult.value = await response.json();
  } catch (error) {
    // показать ошибку
  } finally {
    testing.value = false;
  }
};
</script>
```

### Task 1.4: Сохранение новых полей (10 минут)

При создании/обновлении tool включить новые поля в запрос:

```typescript
const saveTool = async () => {
  await fetch('/tools', {
    method: 'POST',
    body: JSON.stringify({
      name: tool.name,
      description: tool.description,
      endpoint: tool.endpoint,
      http_method: tool.http_method || 'POST',      // ✨
      execution_type: tool.execution_type,
      auth_type: tool.auth_type,
      input_schema: tool.input_schema,
      parameter_mapping: tool.parameter_mapping,    // ✨
      response_transform: tool.response_transform   // ✨
    })
  });
};
```

**Результат Phase 1**: Можно создавать GET/POST tools, тестировать их, видеть ответ.

---

## 📋 Phase 2: Визуальный конструктор (1-2 дня)

Упрощённый UI без написания JSON Schema вручную.

### Task 2.1: Построение дерева полей из ответа (2 часа)

После тестового вызова показать дерево полей:

```typescript
interface FieldNode {
  path: string;         // 'data.orders[].id'
  key: string;          // 'id'
  type: string;         // 'string' | 'number' | 'array' | 'object'
  example: any;
  selected: boolean;
  rename: string;
  children?: FieldNode[];
}

function buildFieldTree(obj: any, prefix = ''): FieldNode[] {
  if (!obj || typeof obj !== 'object') return [];
  
  if (Array.isArray(obj)) {
    if (obj.length === 0) return [];
    return buildFieldTree(obj[0], `${prefix}[]`);
  }
  
  return Object.entries(obj).map(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    const node: FieldNode = {
      path,
      key,
      type: Array.isArray(value) ? 'array' : typeof value,
      example: typeof value === 'object' ? undefined : value,
      selected: true,
      rename: key
    };
    
    if (typeof value === 'object' && value !== null) {
      node.children = buildFieldTree(value, path);
    }
    
    return node;
  });
}
```

**UI компонент**:
```vue
<template>
  <div class="field-tree">
    <FieldNode 
      v-for="field in fields" 
      :key="field.path"
      :field="field"
      @toggle="handleToggle"
      @rename="handleRename"
    />
  </div>
</template>
```

### Task 2.2: Генерация response_transform (1 час)

```typescript
function generateResponseTransform(fields: FieldNode[]): ResponseTransform {
  const flatFields: FieldNode[] = [];
  const arrayGroups: Map<string, FieldNode[]> = new Map();
  
  // Flatten и группировка
  const flatten = (nodes: FieldNode[]) => {
    nodes.forEach(node => {
      if (node.selected) {
        if (node.path.includes('[]')) {
          const arrayPath = node.path.split('[]')[0];
          if (!arrayGroups.has(arrayPath)) {
            arrayGroups.set(arrayPath, []);
          }
          arrayGroups.get(arrayPath)!.push(node);
        } else {
          flatFields.push(node);
        }
      }
      if (node.children) flatten(node.children);
    });
  };
  
  flatten(fields);
  
  return {
    mode: 'fields',
    fields: flatFields.map(f => ({
      source: f.path,
      target: f.rename
    })),
    arrays: Array.from(arrayGroups.entries()).map(([source, fields]) => ({
      source,
      target: source.split('.').pop() || 'items',
      fields: fields.map(f => ({
        source: f.path.split('[]')[1]?.slice(1) || f.key,
        target: f.rename
      }))
    }))
  };
}
```

### Task 2.3: Live preview (1 час)

Применить фильтр локально для показа результата:

```typescript
function applyTransformLocally(
  raw: any, 
  transform: ResponseTransform
): any {
  if (transform.mode === 'jmespath') {
    // Используйте библиотеку jmespath.js
    const jmespath = await import('jmespath');
    return jmespath.search(raw, transform.expression || '@');
  }
  
  if (transform.mode === 'fields') {
    const result: any = {};
    
    // Простые поля
    transform.fields?.forEach(({source, target}) => {
      result[target] = resolvePath(raw, source);
    });
    
    // Массивы
    transform.arrays?.forEach(({source, target, fields}) => {
      const arr = resolvePath(raw, source);
      if (Array.isArray(arr)) {
        result[target] = arr.map(item => {
          const newItem: any = {};
          fields.forEach(({source: s, target: t}) => {
            newItem[t] = resolvePath(item, s);
          });
          return newItem;
        });
      }
    });
    
    return result;
  }
  
  return raw;
}

function resolvePath(obj: any, path: string): any {
  return path.split('.').reduce((curr, key) => curr?.[key], obj);
}
```

**Результат Phase 2**: Визуальный выбор полей, live preview, экономия токенов.

---

## 📋 Phase 3: Parameter Mapping UI (1 день)

Визуальное указание, куда идёт каждый параметр.

### Task 3.1: Автоопределение path параметров

```typescript
// При изменении URL автоматически находить {placeholders}
watch(() => tool.endpoint, (url) => {
  if (!url) return;
  
  const pathParams = extractPathParams(url);
  
  // Автоматически создать параметры
  pathParams.forEach(paramName => {
    if (!parameters.find(p => p.name === paramName)) {
      parameters.push({
        name: paramName,
        type: 'string',
        location: 'path',  // автоматически
        required: true,
        description: ''
      });
    }
  });
  
  // Обновить parameter_mapping
  updateParameterMapping();
});

function extractPathParams(url: string): string[] {
  const regex = /\{([^}]+)\}/g;
  return [...url.matchAll(regex)].map(m => m[1]);
}
```

### Task 3.2: UI для каждого параметра

```vue
<div v-for="param in parameters" :key="param.name" class="parameter">
  <Input v-model="param.name" label="Имя" />
  
  <Select v-model="param.type" label="Тип">
    <option value="string">String</option>
    <option value="integer">Integer</option>
    <option value="boolean">Boolean</option>
  </Select>
  
  <!-- ✨ Главное - выбор расположения -->
  <RadioGroup v-model="param.location" label="Где">
    <Radio value="path" :disabled="!isInUrl(param.name)">
      Path (в URL)
    </Radio>
    <Radio value="query">Query (?param=value)</Radio>
    <Radio value="body">Body (JSON)</Radio>
  </RadioGroup>
  
  <Textarea 
    v-model="param.description" 
    label="Описание для LLM"
    placeholder="Это поле LLM читает, чтобы понять что передать"
    required
  />
</div>
```

**Результат Phase 3**: Полный контроль над параметрами, автоопределение path params.

---

## 📋 Phase 4: Polish (1-2 дня)

Доведение до уровня n8n.

- Tree view для JSON
- JMESPath редактор
- Fields ↔ JSON переключение
- Drag-and-drop параметров
- Валидация в реальном времени
- Клонирование tool

---

## 🚀 Быстрый старт (для тестирования)

### 1. Проверить, что backend работает

```bash
# Применить миграцию (если ещё не применена)
cd /root/agentsapp/backend
pip install jmespath>=1.0
alembic upgrade head

# Перезапустить
docker-compose restart backend

# Проверить
curl http://localhost:8000/health
```

### 2. Импортировать Postman коллекцию

Файл: `/root/agentsapp/backend/http_tools_api.postman_collection.json`

Содержит 7 готовых запросов для тестирования всех новых возможностей.

### 3. Посмотреть примеры

**Файлы с примерами**:
- `backend/example_http_tool.json` - примеры конфигураций tool
- `backend/TESTING_GUIDE.md` - curl команды для ручного тестирования
- `backend/test_http_tools.sh` - автоматический тест всех endpoints

### 4. Открыть Swagger UI

```
http://localhost:8000/docs
```

Найдите endpoints:
- `POST /tools/test` - тестовый вызов
- `POST /tools/{tool_id}/test` - тест сохранённого
- `POST /tools` - создание (теперь с новыми полями)

Каждый endpoint содержит описание и примеры.

---

## 📊 Приоритеты реализации

| Что | Сложность | Польза | Приоритет |
|-----|-----------|--------|-----------|
| HTTP method выбор | Низкая | Высокая | 🔴 Высокий |
| Кнопка "Тестировать" | Средняя | Высокая | 🔴 Высокий |
| Показ raw_body | Низкая | Высокая | 🔴 Высокий |
| Сохранение новых полей | Низкая | Высокая | 🔴 Высокий |
| Построение дерева полей | Средняя | Средняя | 🟡 Средний |
| Чекбоксы фильтра | Средняя | Высокая | 🟡 Средний |
| Live preview фильтра | Средняя | Средняя | 🟡 Средний |
| Parameter mapping UI | Средняя | Средняя | 🟡 Средний |
| JMESPath режим | Средняя | Низкая | 🟢 Низкий |
| Tree view JSON | Высокая | Средняя | 🟢 Низкий |

---

## 🎨 UI/UX Reference (как в n8n)

### Референсы

1. **n8n HTTP Request node** - https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.httprequest/
2. **Postman Request Builder**
3. **Insomnia HTTP Client**

### Ключевые паттерны

- **Tabs для режимов**: Fields | JSON | JMESPath
- **Live preview**: показывать результат сразу при изменении
- **Collapsible sections**: HTTP Config, Parameters, Auth, Response Filter
- **Badge с метриками**: "−93% токенов", "142ms", "200 OK"
- **Tree view**: раскрывающиеся объекты/массивы

---

## 🧪 Простой способ проверить backend

### Без UI, через curl:

```bash
# 1. Протестировать GET
curl -X POST http://localhost:8000/tools/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @- << 'EOF'
{
  "endpoint": "https://api.github.com/users/{username}",
  "http_method": "GET",
  "args": {"username": "torvalds"},
  "parameter_mapping": {"username": "path"},
  "auth_type": "none"
}
EOF

# Должен вернуть:
# {
#   "status_code": 200,
#   "raw_body": {...профиль GitHub...},
#   "request_url": "https://api.github.com/users/torvalds",
#   "request_method": "GET"
# }

# 2. То же, но с фильтрацией
curl -X POST http://localhost:8000/tools/test \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d @- << 'EOF'
{
  "endpoint": "https://api.github.com/users/{username}",
  "http_method": "GET",
  "args": {"username": "torvalds"},
  "parameter_mapping": {"username": "path"},
  "auth_type": "none",
  "response_transform": {
    "mode": "fields",
    "fields": [
      {"source": "login", "target": "username"},
      {"source": "name", "target": "full_name"}
    ]
  }
}
EOF

# Должен вернуть:
# {
#   "raw_body": {...50+ полей...},
#   "transformed_body": {"username": "torvalds", "full_name": "Linus Torvalds"},
#   "raw_size_bytes": 2500,
#   "transformed_size_bytes": 80
# }
```

---

## ❓ FAQ

### Q: Нужно ли обновлять существующий UI для tools?
**A**: Нет, если не хотите. Новые поля опциональные (default: POST, null, null). Старые tools продолжат работать.

### Q: Можно ли начать с GET, а POST добавить позже?
**A**: Да! Реализуйте только GET в Phase 1, остальные методы добавите потом.

### Q: Обязательно ли делать фильтр ответов?
**A**: Нет, но это даёт огромную экономию токенов (50-95%). Можно отложить на Phase 2.

### Q: Нужна ли библиотека для JMESPath на фронте?
**A**: Только если хотите показывать live preview JMESPath фильтра. Для базового функционала не нужна — фильтр применяется на backend.

### Q: Как показывать большие JSON (10KB+)?
**A**: Используйте виртуализацию (react-window, vue-virtual-scroller) или ленивую загрузку узлов дерева.

---

## ✅ Ready to integrate!

- ✅ Backend готов и протестирован
- ✅ Миграция БД применена
- ✅ API endpoints задокументированы
- ✅ TypeScript типы готовы
- ✅ Примеры запросов в Postman коллекции
- ✅ Bash скрипты для тестирования

Можете начинать интеграцию прямо сейчас! 🎉
