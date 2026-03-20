# Схема данных ответа Run API

## Эндпоинт: `POST /api/v1/runs`

### Схема ответа (RunRead)

```typescript
interface RunResponse {
  // Идентификаторы
  id: string;                    // UUID запуска
  tenant_id: string;             // UUID арендатора
  agent_id: string;              // UUID агента
  session_id: string;            // ID сессии диалога (для истории сообщений)
  trace_id: string;             // ID для трассировки запроса

  // Статус выполнения
  status: "queued" | "running" | "succeeded" | "failed";

  // Сообщения
  input_message: string;         // Входное сообщение пользователя
  output_message: string | null; // Ответ агента (null если статус != "succeeded")
  error_message: string | null; // Сообщение об ошибке (null если статус != "failed")

  // Метаданные
  messages: Array<Message> | null; // Полная история сообщений от pydantic-ai (JSONB)
  
  // Использование токенов LLM
  prompt_tokens: number | null;      // Количество токенов во входном промпте
  completion_tokens: number | null; // Количество токенов в ответе
  total_tokens: number | null;      // Общее количество токенов (prompt + completion)

  // Вызванные инструменты
  tools_called: Array<ToolCall> | null; // Список инструментов, вызванных агентом

  // Временные метки
  created_at: string;            // ISO 8601: "2024-01-01T00:00:00Z"
  updated_at: string | null;     // ISO 8601: "2024-01-01T00:00:01Z" или null
}

interface ToolCall {
  name: string;                 // Имя вызванного инструмента
  tool_call_id: string | null;  // ID вызова инструмента (для связи с результатом)
  args: Record<string, any>;    // Аргументы, переданные инструменту
}

interface Message {
  // Структура сообщения от pydantic-ai
  // Может быть ModelRequest, ModelResponse, UserMessage и т.д.
  [key: string]: any;
}
```

## Примеры ответов

### Успешный ответ

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "agent_id": "789e0123-e45b-67c8-d901-234567890abc",
  "session_id": "session-12345",
  "status": "succeeded",
  "input_message": "Какая погода в Москве?",
  "output_message": "В Москве сейчас солнечно, температура 22°C",
  "trace_id": "trace-abc123",
  "created_at": "2024-01-27T10:30:00Z",
  "updated_at": "2024-01-27T10:30:05Z",
  "error_message": null,
  "messages": [
    {
      "parts": [
        {
          "part_kind": "user-prompt",
          "content": "Какая погода в Москве?"
        }
      ]
    },
    {
      "parts": [
        {
          "part_kind": "tool-call",
          "tool_name": "weather_api",
          "tool_call_id": "call_123",
          "args": {
            "city": "Moscow"
          }
        }
      ]
    },
    {
      "parts": [
        {
          "part_kind": "text",
          "content": "В Москве сейчас солнечно, температура 22°C"
        }
      ]
    }
  ],
  "prompt_tokens": 150,
  "completion_tokens": 50,
  "total_tokens": 200,
  "tools_called": [
    {
      "name": "weather_api",
      "tool_call_id": "call_123",
      "args": {
        "city": "Moscow"
      }
    }
  ]
}
```

### Ответ с ошибкой

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "agent_id": "789e0123-e45b-67c8-d901-234567890abc",
  "session_id": "session-12345",
  "status": "failed",
  "input_message": "Какая погода в Москве?",
  "output_message": null,
  "trace_id": "trace-abc123",
  "created_at": "2024-01-27T10:30:00Z",
  "updated_at": "2024-01-27T10:30:02Z",
  "error_message": "Tool execution error: Connection timeout",
  "messages": null,
  "prompt_tokens": null,
  "completion_tokens": null,
  "total_tokens": null,
  "tools_called": null
}
```

### Ответ без вызова инструментов

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
  "agent_id": "789e0123-e45b-67c8-d901-234567890abc",
  "session_id": "session-12345",
  "status": "succeeded",
  "input_message": "Привет!",
  "output_message": "Привет! Чем могу помочь?",
  "trace_id": "trace-abc123",
  "created_at": "2024-01-27T10:30:00Z",
  "updated_at": "2024-01-27T10:30:01Z",
  "error_message": null,
  "messages": [
    {
      "parts": [
        {
          "part_kind": "user-prompt",
          "content": "Привет!"
        }
      ]
    },
    {
      "parts": [
        {
          "part_kind": "text",
          "content": "Привет! Чем могу помочь?"
        }
      ]
    }
  ],
  "prompt_tokens": 10,
  "completion_tokens": 8,
  "total_tokens": 18,
  "tools_called": []
}
```

## Описание полей

### Обязательные поля

- `id` - Уникальный идентификатор запуска
- `tenant_id` - Идентификатор арендатора
- `agent_id` - Идентификатор агента
- `session_id` - Идентификатор сессии (для группировки сообщений в диалог)
- `status` - Статус выполнения
- `input_message` - Входное сообщение пользователя
- `trace_id` - ID для трассировки и логирования
- `created_at` - Время создания

### Условные поля

- `output_message` - Заполняется только при `status === "succeeded"`
- `error_message` - Заполняется только при `status === "failed"`
- `prompt_tokens`, `completion_tokens`, `total_tokens` - Заполняются, если LLM предоставил информацию о токенах
- `tools_called` - Массив вызовов инструментов (может быть пустым `[]`, если инструменты не вызывались)
- `messages` - Полная история сообщений (может быть `null` при ошибке)

### Поля для аналитики

- `prompt_tokens` - Используется для расчета стоимости запросов
- `completion_tokens` - Используется для расчета стоимости ответов
- `total_tokens` - Общее потребление токенов
- `tools_called` - Список использованных инструментов для аналитики и отладки

## Использование на фронтенде

```typescript
// TypeScript пример
interface RunResponse {
  id: string;
  tenant_id: string;
  agent_id: string;
  session_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  input_message: string;
  output_message: string | null;
  trace_id: string;
  created_at: string;
  updated_at: string | null;
  error_message: string | null;
  messages: any[] | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
  tools_called: Array<{
    name: string;
    tool_call_id: string | null;
    args: Record<string, any>;
  }> | null;
}

// Использование
const response = await fetch('/api/v1/runs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    agent_id: '...',
    input_message: 'Привет!'
  })
});

const run: RunResponse = await response.json();

// Проверка статуса
if (run.status === 'succeeded') {
  console.log('Ответ:', run.output_message);
  console.log('Токены:', run.total_tokens);
  console.log('Инструменты:', run.tools_called);
} else if (run.status === 'failed') {
  console.error('Ошибка:', run.error_message);
}
```
