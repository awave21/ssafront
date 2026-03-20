# ТЗ Backend: Справочники (Directories)

## Обзор

Справочники — это структурированные наборы данных, которые автоматически становятся инструментами (tools) агента. Каждый справочник превращается в функцию, которую агент может вызывать для получения информации.

## Модели данных

### Directory (Справочник)

```python
class Directory:
    id: UUID
    tenant_id: UUID
    agent_id: UUID                    # FK на agents
    
    # Основные поля
    name: str                         # "Услуги клиники"
    slug: str                         # "uslugi-kliniki" (уникальный в рамках агента)
    tool_name: str                    # "get_services" (имя функции для агента)
    tool_description: str             # "Найти услугу по названию или описанию"
    
    # Шаблон и структура
    template: DirectoryTemplate       # qa, service_catalog, product_catalog, company_info, custom
    columns: list[ColumnDefinition]   # JSON: определение колонок
    
    # Настройки поведения
    response_mode: ResponseMode       # function_result | direct_message
    search_type: SearchType           # exact | fuzzy | semantic
    is_enabled: bool                  # Включён/выключен
    
    # Метаданные
    items_count: int                  # Кэшированное количество записей
    created_at: datetime
    updated_at: datetime
```

### DirectoryItem (Запись справочника)

```python
class DirectoryItem:
    id: UUID
    tenant_id: UUID
    directory_id: UUID                # FK на directories
    
    data: dict                        # JSON: данные по колонкам {"name": "...", "price": 1000}
    embedding: list[float] | None     # Вектор для семантического поиска (1536 dim)
    
    created_at: datetime
    updated_at: datetime
```

### Вспомогательные типы

```python
class DirectoryTemplate(str, Enum):
    QA = "qa"                         # Вопрос-ответ
    SERVICE_CATALOG = "service_catalog"
    PRODUCT_CATALOG = "product_catalog"
    COMPANY_INFO = "company_info"
    CUSTOM = "custom"

class ResponseMode(str, Enum):
    FUNCTION_RESULT = "function_result"   # Агент получает данные и формулирует ответ
    DIRECT_MESSAGE = "direct_message"     # Ответ отправляется напрямую пользователю

class SearchType(str, Enum):
    EXACT = "exact"                   # Точное совпадение ключевых слов
    FUZZY = "fuzzy"                   # Нечёткий поиск (опечатки)
    SEMANTIC = "semantic"             # Семантический поиск по embeddings

class ColumnType(str, Enum):
    # Текст
    TEXT = "text"                     # Неограниченный текст
    VARCHAR = "varchar"               # Строка до 255 символов
    
    # Числа
    INTEGER = "integer"               # Целое число (-2147483648 to +2147483647)
    BIGINT = "bigint"                 # Большое целое число
    NUMERIC = "numeric"               # Число с фиксированной точностью (для цен)
    
    # Дата и время
    DATE = "date"                     # Только дата (YYYY-MM-DD)
    TIMESTAMP = "timestamp"           # Дата и время (YYYY-MM-DD HH:MM:SS)
    TIME = "time"                     # Только время (HH:MM:SS)
    
    # Другие
    BOOLEAN = "boolean"               # true/false
    JSON = "json"                     # JSON объект
    UUID = "uuid"                     # UUID
    URL = "url"                       # URL (валидируется)

class ColumnDefinition:
    name: str                         # "price" — slug для кода
    label: str                        # "Цена" — отображаемое название
    type: ColumnType                  # Тип данных PostgreSQL
    required: bool                    # Обязательное поле
    searchable: bool                  # Участвует в поиске
```

### Предустановленные колонки по шаблонам

Шаблоны используются как начальная конфигурация. Пользователь может изменить колонки после создания.

```python
TEMPLATE_COLUMNS = {
    "qa": [
        {"name": "question", "label": "Вопрос", "type": "text", "required": True, "searchable": True},
        {"name": "answer", "label": "Ответ", "type": "text", "required": True, "searchable": False},
    ],
    "service_catalog": [
        {"name": "name", "label": "Название", "type": "text", "required": True, "searchable": True},
        {"name": "description", "label": "Описание", "type": "text", "required": False, "searchable": True},
        {"name": "price", "label": "Цена", "type": "numeric", "required": False, "searchable": False},
    ],
    "product_catalog": [
        {"name": "name", "label": "Название", "type": "text", "required": True, "searchable": True},
        {"name": "description", "label": "Описание", "type": "text", "required": False, "searchable": True},
        {"name": "price", "label": "Цена", "type": "numeric", "required": False, "searchable": False},
        {"name": "specs", "label": "Характеристики", "type": "text", "required": False, "searchable": True},
    ],
    "company_info": [
        {"name": "topic", "label": "Тема", "type": "text", "required": True, "searchable": True},
        {"name": "info", "label": "Информация", "type": "text", "required": True, "searchable": True},
    ],
    "custom": []  # Пользователь задаёт колонки самостоятельно
}
```

---

## API Endpoints

### Справочники

#### `GET /agents/{agent_id}/directories`

Получение списка справочников агента.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Услуги клиники",
    "slug": "uslugi-kliniki",
    "tool_name": "get_services",
    "tool_description": "Найти услугу по названию",
    "template": "service_catalog",
    "columns": [...],
    "response_mode": "function_result",
    "search_type": "fuzzy",
    "is_enabled": true,
    "items_count": 47,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
]
```

---

#### `POST /agents/{agent_id}/directories`

Создание нового справочника.

**Request:**
```json
{
  "name": "Услуги клиники",
  "tool_name": "get_services",
  "tool_description": "Найти услугу клиники по названию, категории или описанию",
  "template": "service_catalog",
  "columns": [
    {"name": "name", "label": "Название", "type": "text", "required": true, "searchable": true},
    {"name": "description", "label": "Описание", "type": "text", "required": false, "searchable": true},
    {"name": "price", "label": "Цена", "type": "numeric", "required": false, "searchable": false}
  ],
  "response_mode": "function_result",
  "search_type": "fuzzy"
}
```

**Логика колонок:**
- Если `columns` передан — использовать их
- Если `columns` = null и `template` != "custom" — использовать колонки из `TEMPLATE_COLUMNS[template]`
- Если `columns` = null и `template` = "custom" — ошибка 400

**Валидация:**
- `name`: 1-200 символов, обязательное
- `tool_name`: латиница, цифры, `_`, уникальное в рамках агента, обязательное
- `template`: одно из допустимых значений
- `columns`: массив ColumnDefinition, минимум 1, максимум 15 колонок
- `columns[].name`: уникальный в рамках справочника, `^[a-z][a-z0-9_]*$`
- `columns[].type`: одно из допустимых значений ColumnType

**Response:** Созданный справочник (201)

---

#### `GET /agents/{agent_id}/directories/{directory_id}`

Получение справочника по ID.

**Response:** Объект справочника

---

#### `PUT /agents/{agent_id}/directories/{directory_id}`

Обновление справочника.

**Request:**
```json
{
  "name": "Услуги клиники (обновлено)",
  "tool_name": "get_clinic_services",
  "tool_description": "Новое описание",
  "response_mode": "direct_message",
  "search_type": "semantic",
  "is_enabled": false,
  "columns": [
    {"name": "name", "label": "Название услуги", "type": "text", "required": true, "searchable": true},
    {"name": "description", "label": "Описание", "type": "text", "required": false, "searchable": true},
    {"name": "price", "label": "Стоимость", "type": "numeric", "required": true, "searchable": false},
    {"name": "duration", "label": "Длительность (мин)", "type": "integer", "required": false, "searchable": false}
  ]
}
```

**Изменение колонок:**
- `template` нельзя изменить после создания
- `columns` МОЖНО изменить:
  - Добавить новые колонки
  - Удалить существующие колонки (данные в этих колонках будут потеряны!)
  - Изменить `label`, `type`, `required`, `searchable`
  - Изменить `name` колонки (данные мигрируются автоматически)

**Миграция данных при изменении колонок:**
1. При удалении колонки — удалить поле из всех `directory_items.data`
2. При переименовании колонки — переименовать ключ в `directory_items.data`
3. При изменении типа — попытаться конвертировать данные (если невозможно — оставить как есть)

**Response:** Обновлённый справочник

---

#### `DELETE /agents/{agent_id}/directories/{directory_id}`

Удаление справочника (и всех его записей).

**Response:** 204 No Content

---

#### `PATCH /agents/{agent_id}/directories/{directory_id}/toggle`

Быстрое включение/выключение справочника.

**Request:**
```json
{
  "is_enabled": true
}
```

**Response:** Обновлённый справочник

---

### Записи справочника

#### `GET /agents/{agent_id}/directories/{directory_id}/items`

Получение записей справочника с пагинацией и поиском.

**Query параметры:**
- `limit`: int (default 50, max 100)
- `offset`: int (default 0)
- `search`: string (поиск по searchable колонкам)

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "data": {
        "name": "Консультация",
        "description": "Первичный приём врача",
        "price": 2000
      },
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 47,
  "limit": 50,
  "offset": 0
}
```

---

#### `POST /agents/{agent_id}/directories/{directory_id}/items`

Добавление одной записи.

**Request:**
```json
{
  "data": {
    "name": "Консультация",
    "description": "Первичный приём врача",
    "price": 2000
  }
}
```

**Валидация данных:**
- Проверка обязательных полей согласно `columns[].required`
- Проверка типов данных согласно `columns[].type`:

| Тип | Валидация | Примеры |
|-----|-----------|---------|
| `text` | любая строка | "Описание услуги" |
| `varchar` | строка до 255 символов | "Короткий текст" |
| `integer` | целое число | 42, -100 |
| `bigint` | большое целое число | 9999999999 |
| `numeric` | число с точкой | 1500.50, 99.99 |
| `date` | ISO дата | "2024-01-15" |
| `timestamp` | ISO datetime | "2024-01-15T14:30:00Z" |
| `time` | время | "14:30:00" |
| `boolean` | true/false | true, false |
| `json` | валидный JSON | {"key": "value"} |
| `uuid` | UUID формат | "550e8400-e29b-41d4-a716-446655440000" |
| `url` | валидный URL | "https://example.com" |

**Response:** Созданная запись (201)

---

#### `POST /agents/{agent_id}/directories/{directory_id}/items/bulk`

Массовое добавление записей (для импорта).

**Request:**
```json
{
  "items": [
    {"data": {"name": "Консультация", "price": 2000}},
    {"data": {"name": "УЗИ", "price": 1500}}
  ],
  "replace_all": false  // true = удалить все существующие перед добавлением
}
```

**Response:**
```json
{
  "created": 125,
  "errors": [
    {"row": 15, "error": "Поле 'name' обязательно"},
    {"row": 23, "error": "Поле 'price' должно быть числом"}
  ]
}
```

---

#### `PUT /agents/{agent_id}/directories/{directory_id}/items/{item_id}`

Обновление записи.

**Request:**
```json
{
  "data": {
    "name": "Консультация (обновлено)",
    "price": 2500
  }
}
```

**Response:** Обновлённая запись

---

#### `DELETE /agents/{agent_id}/directories/{directory_id}/items/{item_id}`

Удаление одной записи.

**Response:** 204 No Content

---

#### `DELETE /agents/{agent_id}/directories/{directory_id}/items`

Массовое удаление записей.

**Request:**
```json
{
  "ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:** 204 No Content

---

### Импорт/Экспорт

#### `POST /agents/{agent_id}/directories/{directory_id}/import`

Импорт из CSV/Excel файла.

**Request:** `multipart/form-data`
- `file`: файл (.csv или .xlsx)
- `mapping`: JSON string — маппинг колонок
- `has_header`: bool (default true)
- `replace_all`: bool (default false)

**Пример mapping:**
```json
{
  "Наименование": "name",
  "Описание услуги": "description", 
  "Стоимость": "price",
  "Артикул": null  // пропустить
}
```

**Response:**
```json
{
  "created": 125,
  "skipped": 3,
  "errors": [
    {"row": 15, "error": "Поле 'name' обязательно"}
  ]
}
```

---

#### `GET /agents/{agent_id}/directories/{directory_id}/export`

Экспорт в CSV.

**Query параметры:**
- `format`: "csv" | "xlsx" (default "csv")

**Response:** Файл для скачивания

**Headers:**
```
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename="uslugi-kliniki.csv"
```

---

#### `POST /agents/{agent_id}/directories/{directory_id}/import/preview`

Превью импорта (парсинг файла без сохранения).

**Request:** `multipart/form-data`
- `file`: файл

**Response:**
```json
{
  "columns": ["Наименование", "Описание услуги", "Стоимость", "Артикул"],
  "rows_count": 128,
  "preview": [
    ["Консультация", "Первичный приём", "2000", "SRV-001"],
    ["УЗИ", "Ультразвуковое исследование", "1500", "SRV-002"],
    ["Анализы", "Лабораторные анализы", "800", "SRV-003"]
  ],
  "suggested_mapping": {
    "Наименование": "name",
    "Описание услуги": "description",
    "Стоимость": "price",
    "Артикул": null
  }
}
```

---

### Поиск (для runtime агента)

#### `POST /agents/{agent_id}/directories/{directory_id}/search`

Поиск по справочнику (используется агентом и для тестирования).

**Request:**
```json
{
  "query": "консультация кардиолога",
  "limit": 5
}
```

**Response:**
```json
{
  "results": [
    {
      "id": "uuid",
      "data": {
        "name": "Консультация кардиолога",
        "description": "Приём врача-кардиолога",
        "price": 3000
      },
      "relevance": 0.95
    }
  ]
}
```

---

#### `POST /agents/{agent_id}/knowledge/search`

Поиск по ВСЕМ справочникам агента (универсальный).

**Request:**
```json
{
  "query": "как записаться на приём",
  "limit": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "directory_id": "uuid",
      "directory_name": "FAQ",
      "item": {...},
      "relevance": 0.92
    }
  ]
}
```

---

## Интеграция с Runtime агента

### Генерация tools из справочников

При запуске агента система должна:

1. Загрузить все `is_enabled = true` справочники агента
2. Для каждого справочника создать tool:
   - Имя: `directory.tool_name`
   - Описание: `directory.tool_description`
   - Параметры: `query: str` (опционально, зависит от search_type)
3. Зарегистрировать tools в Pydantic AI агенте

### Пример генерации tool

```python
def create_directory_tool(directory: Directory):
    async def tool_fn(ctx: RunContext, query: str = "") -> str:
        results = await search_directory(
            directory_id=directory.id,
            query=query,
            search_type=directory.search_type,
            limit=5
        )
        
        if directory.response_mode == ResponseMode.DIRECT_MESSAGE:
            # Форматируем для прямого ответа пользователю
            return format_direct_response(results, directory.template)
        else:
            # Форматируем для обработки агентом
            return format_function_result(results, directory.template)
    
    tool_fn.__name__ = directory.tool_name
    tool_fn.__doc__ = directory.tool_description
    
    return tool_fn
```

### Форматирование ответов

**function_result (для агента):**
```
Найдено 3 услуги:

1. Консультация кардиолога
   Описание: Приём врача-кардиолога, ЭКГ
   Цена: 3000 ₽

2. УЗИ сердца
   Описание: Эхокардиография
   Цена: 2500 ₽
```

**direct_message (для пользователя):**
```
Консультация кардиолога — 3000 ₽
УЗИ сердца — 2500 ₽
```

---

## Миграции БД

### Создание таблиц

```sql
-- Справочники
CREATE TABLE directories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    tool_description TEXT,
    
    template VARCHAR(50) NOT NULL DEFAULT 'custom',
    columns JSONB NOT NULL DEFAULT '[]',
    
    response_mode VARCHAR(50) NOT NULL DEFAULT 'function_result',
    search_type VARCHAR(50) NOT NULL DEFAULT 'fuzzy',
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    
    items_count INTEGER NOT NULL DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    
    UNIQUE(agent_id, slug),
    UNIQUE(agent_id, tool_name)
);

CREATE INDEX idx_directories_agent ON directories(agent_id);
CREATE INDEX idx_directories_tenant ON directories(tenant_id);

-- Записи справочников
CREATE TABLE directory_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    directory_id UUID NOT NULL REFERENCES directories(id) ON DELETE CASCADE,
    
    data JSONB NOT NULL DEFAULT '{}',
    embedding vector(1536),  -- для семантического поиска
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX idx_directory_items_directory ON directory_items(directory_id);
CREATE INDEX idx_directory_items_tenant ON directory_items(tenant_id);
CREATE INDEX idx_directory_items_embedding ON directory_items 
    USING hnsw (embedding vector_cosine_ops);

-- Полнотекстовый поиск по data
CREATE INDEX idx_directory_items_data_fts ON directory_items 
    USING gin(to_tsvector('russian', data::text));
```

### Триггер для items_count

```sql
CREATE OR REPLACE FUNCTION update_directory_items_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE directories SET items_count = items_count + 1, updated_at = NOW()
        WHERE id = NEW.directory_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE directories SET items_count = items_count - 1, updated_at = NOW()
        WHERE id = OLD.directory_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_directory_items_count
AFTER INSERT OR DELETE ON directory_items
FOR EACH ROW EXECUTE FUNCTION update_directory_items_count();
```

### Миграция данных при изменении колонок

```python
async def migrate_directory_columns(
    directory_id: UUID,
    old_columns: list[ColumnDefinition],
    new_columns: list[ColumnDefinition]
):
    """Мигрирует данные в directory_items при изменении структуры колонок."""
    
    old_names = {c.name for c in old_columns}
    new_names = {c.name for c in new_columns}
    
    # Удалённые колонки
    removed = old_names - new_names
    
    # Если есть удалённые колонки — удаляем их из всех записей
    if removed:
        for col_name in removed:
            await db.execute("""
                UPDATE directory_items 
                SET data = data - $1, updated_at = NOW()
                WHERE directory_id = $2
            """, col_name, directory_id)
    
    # Изменение типов — логируем, но не конвертируем автоматически
    # (данные в JSONB хранятся как есть, валидация происходит при записи)
```

---

## Алгоритмы поиска

### Exact (точный)

```sql
SELECT * FROM directory_items
WHERE directory_id = $1
  AND (
    data->>'name' ILIKE '%' || $2 || '%'
    OR data->>'description' ILIKE '%' || $2 || '%'
  )
LIMIT $3;
```

### Fuzzy (нечёткий)

```sql
SELECT *, 
    similarity(data->>'name', $2) as sim_name,
    similarity(data->>'description', $2) as sim_desc
FROM directory_items
WHERE directory_id = $1
  AND (
    similarity(data->>'name', $2) > 0.3
    OR similarity(data->>'description', $2) > 0.3
  )
ORDER BY GREATEST(sim_name, sim_desc) DESC
LIMIT $3;
```

Требует: `CREATE EXTENSION pg_trgm;`

### Semantic (семантический)

```sql
SELECT *, 1 - (embedding <=> $2::vector) as relevance
FROM directory_items
WHERE directory_id = $1
  AND embedding IS NOT NULL
ORDER BY embedding <=> $2::vector
LIMIT $3;
```

Требует: `CREATE EXTENSION vector;` (pgvector)

---

## Создание embeddings

При создании/обновлении записи с `search_type = semantic`:

```python
async def create_item_embedding(item: DirectoryItem, directory: Directory):
    # Собираем текст из searchable полей
    searchable_columns = [c for c in directory.columns if c.searchable]
    text_parts = [str(item.data.get(c.name, "")) for c in searchable_columns]
    text = " ".join(text_parts)
    
    # Создаём embedding через OpenAI
    response = await openai.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    
    return response.data[0].embedding
```

---

## Обработка ошибок

| Код | Ситуация |
|-----|----------|
| 400 | Невалидные данные (tool_name, обязательные поля) |
| 404 | Справочник или запись не найдены |
| 409 | tool_name или slug уже существует у агента |
| 413 | Файл импорта слишком большой |
| 422 | Ошибка парсинга CSV/Excel |

---

## Лимиты

| Параметр | Значение |
|----------|----------|
| Справочников на агента | 20 |
| Записей в справочнике | 10 000 |
| Размер файла импорта | 10 МБ |
| Колонок в справочнике | 15 |
| Длина tool_name | 100 символов |
| Длина tool_description | 500 символов |
| Длина column.name | 50 символов |
| Длина column.label | 100 символов |

## Поддерживаемые типы колонок

| Тип | PostgreSQL аналог | Описание |
|-----|-------------------|----------|
| `text` | TEXT | Неограниченный текст |
| `varchar` | VARCHAR(255) | Строка до 255 символов |
| `integer` | INTEGER | Целое число |
| `bigint` | BIGINT | Большое целое |
| `numeric` | NUMERIC(15,2) | Число с 2 знаками после точки |
| `date` | DATE | Дата |
| `timestamp` | TIMESTAMPTZ | Дата и время с таймзоной |
| `time` | TIME | Время |
| `boolean` | BOOLEAN | Булево значение |
| `json` | JSONB | JSON объект |
| `uuid` | UUID | UUID |
| `url` | TEXT + валидация | URL адрес |
