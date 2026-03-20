# Схема данных ответа на запрос запуска агента

## `POST /api/v1/runs` - Ответ

### Полная схема данных

```typescript
interface RunResponse {
  // Идентификаторы
  id: string;                    // UUID запуска
  tenant_id: string;             // UUID арендатора
  agent_id: string;              // UUID агента
  session_id: string;            // UUID сессии (для контекста диалога)
  trace_id: string;              // UUID для трейсинга запроса
  
  // Статус и сообщения
  status: "succeeded" | "failed" | "running" | "queued";
  input_message: string;         // Входное сообщение пользователя
  output_message: string | null; // Ответ агента (null если статус не succeeded)
  error_message: string | null;  // Сообщение об ошибке (null если нет ошибки)
  
  // Токены LLM
  prompt_tokens: number | null;      // Количество токенов во входном промпте
  completion_tokens: number | null;  // Количество токенов в ответе
  total_tokens: number | null;       // Общее количество токенов
  
  // Инструменты
  tools_called: Array<{
    name: string;                // Название вызванного инструмента
    tool_call_id: string | null; // ID вызова инструмента
    args: Record<string, any>;   // Аргументы, переданные инструменту
  }> | null;
  
  // Метаданные
  messages: Array<any> | null;   // Полная история сообщений от pydantic-ai (опционально)
  created_at: string;            // ISO 8601 timestamp создания
  updated_at: string | null;     // ISO 8601 timestamp обновления
}
```

### Пример ответа (успешный)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "agent_id": "00000000-0000-0000-0000-000000000002",
  "session_id": "00000000-0000-0000-0000-000000000003",
  "trace_id": "00000000-0000-0000-0000-000000000004",
  "status": "succeeded",
  "input_message": "Hello, please use the weather tool to get current weather in Moscow",
  "output_message": "The current weather in Moscow is sunny, 22°C",
  "error_message": null,
  "prompt_tokens": 150,
  "completion_tokens": 45,
  "total_tokens": 195,
  "tools_called": [
    {
      "name": "get_weather",
      "tool_call_id": "call_abc123",
      "args": {
        "city": "Moscow"
      }
    }
  ],
  "messages": null,
  "created_at": "2024-01-27T10:00:00Z",
  "updated_at": "2024-01-27T10:00:01Z"
}
```

### Пример ответа (ошибка)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "agent_id": "00000000-0000-0000-0000-000000000002",
  "session_id": "00000000-0000-0000-0000-000000000003",
  "trace_id": "00000000-0000-0000-0000-000000000004",
  "status": "failed",
  "input_message": "Hello, please use the weather tool",
  "output_message": null,
  "error_message": "Tool execution failed: Connection timeout",
  "prompt_tokens": 120,
  "completion_tokens": null,
  "total_tokens": null,
  "tools_called": [
    {
      "name": "get_weather",
      "tool_call_id": "call_abc123",
      "args": {
        "city": "Moscow"
      }
    }
  ],
  "messages": null,
  "created_at": "2024-01-27T10:00:00Z",
  "updated_at": "2024-01-27T10:00:05Z"
}
```

### Пример ответа (без токенов)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "00000000-0000-0000-0000-000000000001",
  "agent_id": "00000000-0000-0000-0000-000000000002",
  "session_id": "00000000-0000-0000-0000-000000000003",
  "trace_id": "00000000-0000-0000-0000-000000000004",
  "status": "succeeded",
  "input_message": "Hello",
  "output_message": "Hi! How can I help you?",
  "error_message": null,
  "prompt_tokens": null,
  "completion_tokens": null,
  "total_tokens": null,
  "tools_called": null,
  "messages": null,
  "created_at": "2024-01-27T10:00:00Z",
  "updated_at": "2024-01-27T10:00:01Z"
}
```

## Описание полей

### Идентификаторы

- **id** (string, обязательное) - Уникальный идентификатор запуска агента
- **tenant_id** (string, обязательное) - Идентификатор арендатора (для изоляции данных)
- **agent_id** (string, обязательное) - Идентификатор агента, который выполнил запрос
- **session_id** (string, обязательное) - Идентификатор сессии для поддержания контекста диалога
- **trace_id** (string, обязательное) - Идентификатор для трейсинга запроса в логах

### Статус и сообщения

- **status** (string, обязательное) - Статус выполнения:
  - `"succeeded"` - Успешно выполнено
  - `"failed"` - Ошибка выполнения
  - `"running"` - Выполняется (для асинхронных запросов)
  - `"queued"` - В очереди (для асинхронных запросов)

- **input_message** (string, обязательное) - Исходное сообщение пользователя

- **output_message** (string | null, обязательное) - Ответ агента:
  - Заполнено при `status === "succeeded"`
  - `null` в остальных случаях

- **error_message** (string | null, обязательное) - Сообщение об ошибке:
  - Заполнено при `status === "failed"`
  - `null` в остальных случаях

### Токены LLM

- **prompt_tokens** (number | null, обязательное) - Количество токенов во входном промпте:
  - Включает системный промпт агента
  - Включает историю сообщений сессии
  - Включает текущий запрос пользователя
  - `null` если LLM провайдер не возвращает эту информацию

- **completion_tokens** (number | null, обязательное) - Количество токенов в ответе агента:
  - Токены, сгенерированные LLM
  - `null` если LLM провайдер не возвращает эту информацию

- **total_tokens** (number | null, обязательное) - Общее количество токенов:
  - Сумма `prompt_tokens + completion_tokens`
  - `null` если информация о токенах недоступна

### Инструменты

- **tools_called** (Array | null, обязательное) - Список инструментов, вызванных агентом:
  - `null` если инструменты не вызывались
  - Массив объектов с информацией о каждом вызове:
    - **name** (string) - Название инструмента
    - **tool_call_id** (string | null) - ID вызова инструмента от LLM
    - **args** (Record<string, any>) - Аргументы, переданные инструменту

### Метаданные

- **messages** (Array | null, обязательное) - Полная история сообщений от pydantic-ai:
  - `null` по умолчанию (для экономии трафика)
  - Может быть включена для отладки
  - Содержит полную структуру сообщений, переданных в LLM

- **created_at** (string, обязательное) - ISO 8601 timestamp создания запуска

- **updated_at** (string | null, обязательное) - ISO 8601 timestamp последнего обновления:
  - `null` если еще не обновлялось

## Важные замечания

1. **Токены на верхнем уровне**: Токены находятся на верхнем уровне объекта, а не в вложенном объекте `tokens`

2. **Null значения**: Поля могут быть `null`, если информация недоступна (например, токены от некоторых провайдеров)

3. **Статус и сообщения**: 
   - При `status === "succeeded"` → `output_message` заполнено, `error_message === null`
   - При `status === "failed"` → `error_message` заполнено, `output_message === null`

4. **Инструменты**: `tools_called` может быть `null` даже при успешном выполнении, если агент не вызывал инструменты

5. **Формат дат**: Все даты в формате ISO 8601 (например: `"2024-01-27T10:00:00Z"`)
