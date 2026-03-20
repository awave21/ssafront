# HTTP Tools Enhancement - Backend Implementation Summary

## Реализованные возможности

### ✅ Phase 1: MVP Complete

Backend часть полностью реализована для гибкой работы с HTTP tools:

1. **Поддержка всех HTTP методов** (GET, POST, PUT, PATCH, DELETE)
2. **Parameter mapping** (path/query/body параметры)
3. **Response transformation** (фильтрация ответов для экономии токенов)
4. **Тестовые endpoints** (проверка tool до сохранения)

---

## Изменённые файлы

### 1. База данных

**Файл**: `alembic/versions/0030_tool_http_enhancements.py`
- Миграция добавляет 3 новых поля в таблицу `tools`:
  - `http_method` (String, default='POST')
  - `response_transform` (JSONB, nullable)
  - `parameter_mapping` (JSONB, nullable)

### 2. Модели

**Файл**: `app/db/models/tool.py`
- Добавлены 3 поля в модель `Tool`
- Обратная совместимость сохранена (дефолты)

### 3. Схемы API

**Файл**: `app/schemas/tool.py`
- Обновлены `ToolBase`, `ToolUpdate`
- Добавлены новые схемы:
  - `ToolTestRequest` - для тестовых вызовов
  - `ToolTestResponse` - ответ теста с метриками

### 4. Executor (ядро)

**Файл**: `app/services/tool_executor.py`
- ➕ `_split_params()` - разделение args на path/query/body
- ➕ `_resolve_path()` - извлечение значений по dot-path (поддержка массивов)
- ➕ `transform_response()` - фильтрация ответов (fields/jmespath режимы)
- ➕ `execute_tool_test()` - тестовый вызов с метриками
- ✏️ `execute_tool_call()` - обновлён для поддержки всех HTTP методов

**Ключевые изменения**:
- Динамический `client.request(method, url, ...)` вместо только `client.post()`
- Path params подставляются в URL: `/users/{id}` → `/users/123`
- Query params добавляются в URL
- Body отправляется только для POST/PUT/PATCH

### 5. Runtime integration

**Файл**: `app/services/runtime_tools.py`
- Wrapper tool передаёт `http_method` и `parameter_mapping` в executor
- После получения результата применяется `response_transform`
- LLM получает только отфильтрованный ответ

### 6. API Endpoints

**Файл**: `app/api/routers/tools.py`
- ✏️ Расширена валидация в `_validate_tool_payload()`
- ✏️ `create_tool()` сохраняет новые поля
- ➕ `POST /tools/test` - тест tool до сохранения
- ➕ `POST /tools/{tool_id}/test` - тест сохранённого tool

### 7. Dependencies

**Файл**: `requirements.txt`
- Добавлен `jmespath>=1.0` для поддержки JMESPath режима фильтрации

---

## API Endpoints

### Создание/обновление tool

```http
POST /tools
PUT /tools/{tool_id}

{
  "name": "get_user",
  "description": "Get user from CRM",
  "endpoint": "https://api.example.com/users/{user_id}",
  "http_method": "GET",
  "input_schema": {
    "type": "object",
    "properties": {
      "user_id": {"type": "string", "description": "User ID"}
    },
    "required": ["user_id"]
  },
  "parameter_mapping": {
    "user_id": "path"
  },
  "response_transform": {
    "mode": "fields",
    "fields": [
      {"source": "data.name", "target": "name"},
      {"source": "data.email", "target": "email"}
    ]
  },
  "auth_type": "bearer_token"
}
```

### Тестирование tool (inline)

```http
POST /tools/test

{
  "endpoint": "https://api.example.com/users/{user_id}",
  "http_method": "GET",
  "args": {
    "user_id": "abc-123"
  },
  "parameter_mapping": {
    "user_id": "path"
  },
  "auth_type": "bearer_token",
  "credential_id": "uuid-of-credential",
  "response_transform": {
    "mode": "fields",
    "fields": [
      {"source": "data.name", "target": "name"}
    ]
  }
}
```

**Ответ**:
```json
{
  "status_code": 200,
  "latency_ms": 142,
  "response_headers": {...},
  "raw_body": {"data": {"id": "abc-123", "name": "John", "email": "...", ...}},
  "transformed_body": {"name": "John"},
  "raw_size_bytes": 2500,
  "transformed_size_bytes": 180,
  "error": null,
  "request_url": "https://api.example.com/users/abc-123",
  "request_method": "GET"
}
```

### Тестирование сохранённого tool

```http
POST /tools/{tool_id}/test

{
  "args": {
    "user_id": "abc-123"
  }
}
```

---

## Response Transform Formats

### Fields Mode (визуальный)

```json
{
  "mode": "fields",
  "fields": [
    {"source": "data.name", "target": "name"},
    {"source": "data.orders[].id", "target": "order_ids"}
  ]
}
```

### Arrays Mode (структурированный)

```json
{
  "mode": "fields",
  "arrays": [
    {
      "source": "data.orders",
      "target": "orders",
      "fields": [
        {"source": "id", "target": "order_id"},
        {"source": "price", "target": "price"}
      ]
    }
  ]
}
```

### JMESPath Mode (продвинутый)

```json
{
  "mode": "jmespath",
  "expression": "{name: data.name, orders: data.orders[].{id: id, price: price}}"
}
```

---

## Применение миграции

```bash
# 1. Установить новую зависимость
pip install jmespath>=1.0

# 2. Применить миграцию БД
cd /root/agentsapp/backend
alembic upgrade head

# 3. Перезапустить сервер
# (Docker Compose автоматически перезапустит)
```

---

## Обратная совместимость

✅ Все существующие tools продолжат работать:
- `http_method` по умолчанию = `"POST"`
- `response_transform` = `None` (без фильтрации)
- `parameter_mapping` = `None` (всё в body, как раньше)

---

## Примеры использования

### GET запрос с path параметром

```python
tool = {
    "name": "get_order",
    "endpoint": "https://api.shop.com/orders/{order_id}",
    "http_method": "GET",
    "parameter_mapping": {
        "order_id": "path"
    }
}
# LLM вызовет: GET https://api.shop.com/orders/12345
```

### POST с query и body параметрами

```python
tool = {
    "name": "create_order",
    "endpoint": "https://api.shop.com/orders",
    "http_method": "POST",
    "parameter_mapping": {
        "customer_id": "query",
        "product": "body",
        "quantity": "body"
    }
}
# LLM вызовет: POST https://api.shop.com/orders?customer_id=123
# Body: {"product": "Widget", "quantity": 5}
```

### Фильтрация массива (экономия 90% токенов)

```python
# API возвращает 50 полей на каждый заказ
# С фильтром - только 4 нужных поля

tool = {
    "response_transform": {
        "mode": "fields",
        "arrays": [{
            "source": "data.orders",
            "target": "orders",
            "fields": [
                {"source": "id", "target": "order_id"},
                {"source": "status", "target": "status"},
                {"source": "total", "target": "total"}
            ]
        }]
    }
}
# Результат: 2500 токенов → 250 токенов (-90%)
```

---

## Тестирование

Все файлы успешно прошли проверку:
- ✅ Компиляция Python (syntax check)
- ✅ Linter (no errors)
- ✅ Обратная совместимость сохранена

---

## Что дальше (Frontend)

Теперь нужна реализация на фронте:
1. Визуальный конструктор параметров (Fields/JSON режимы)
2. UI для выбора HTTP метода
3. Маппинг параметров (path/query/body чекбоксы)
4. Панель тестирования с Tree/Raw просмотром
5. Конструктор фильтра ответа (чекбоксы полей)
6. Live preview отфильтрованного ответа
7. Показатель экономии токенов

---

## Готово к использованию! 🎉

Backend полностью готов для создания гибких HTTP tools через API.
