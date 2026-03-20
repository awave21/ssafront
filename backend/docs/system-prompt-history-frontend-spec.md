## История версий системного промпта — фронтендовая спецификация

### 1. Краткий обзор

На странице карточки агента появляется раздел **«История промпта»**. Он позволяет:
- видеть все версии системного промпта (кто, когда, почему изменил);
- просматривать полный текст любой версии;
- откатиться на любую предыдущую версию одним действием;
- создать новую версию вручную с комментарием.

Версии создаются автоматически при каждом изменении `system_prompt` через `PUT /agents/{agent_id}` и при публикации агента. Ручное создание доступно через отдельный эндпоинт.

---

### 2. API-эндпоинты

Базовый путь: `/api/v1/agents/{agent_id}`

| Метод | URL | Scope | Описание |
|-------|-----|-------|----------|
| `GET` | `/system-prompt/history` | `agents:read` | Список версий (пагинация) |
| `GET` | `/system-prompt/current` | `agents:read` | Текущая активная версия |
| `GET` | `/system-prompt/history/{version_id}` | `agents:read` | Детали конкретной версии |
| `POST` | `/system-prompt/history` | `agents:write` | Создать новую версию вручную |
| `POST` | `/system-prompt/history/{version_id}/activate` | `agents:write` | Активировать выбранную версию |

Авторизация: `Authorization: Bearer <token>`, как и все остальные запросы к агентам.

---

### 3. Типы данных

#### 3.1. `SystemPromptVersionListItem` — элемент списка

Возвращается в `GET /system-prompt/history`.

```typescript
type SystemPromptVersionListItem = {
  id: string                   // UUID версии
  agent_id: string             // UUID агента
  version_number: number       // Порядковый номер (1, 2, 3…)
  change_summary: string | null // Комментарий к изменению
  triggered_by: string         // "create" | "update" | "publish" | "manual"
  is_active: boolean           // true = текущая используемая версия
  created_by: string | null    // UUID пользователя, создавшего версию
  created_at: string           // ISO 8601 datetime
  prompt_length: number        // Длина текста промпта в символах
}
```

#### 3.2. `SystemPromptVersionRead` — полная версия

Возвращается в `GET /system-prompt/current`, `GET /system-prompt/history/{version_id}`, `POST /system-prompt/history`, `POST .../activate`.

```typescript
type SystemPromptVersionRead = {
  id: string
  agent_id: string
  tenant_id: string
  version_number: number
  system_prompt: string         // Полный текст промпта
  change_summary: string | null
  triggered_by: string
  is_active: boolean
  created_by: string | null
  created_at: string
  updated_at: string | null
}
```

#### 3.3. `SystemPromptVersionListResponse` — обёртка списка

```typescript
type SystemPromptVersionListResponse = {
  items: SystemPromptVersionListItem[]
  next_cursor: number | null  // version_number для следующей порции, null = данных больше нет
}
```

#### 3.4. `SystemPromptVersionCreate` — тело POST-запроса

```typescript
type SystemPromptVersionCreate = {
  system_prompt: string          // Обязательное. Текст промпта
  change_summary?: string | null // До 500 символов. Комментарий
  activate?: boolean             // По умолчанию true. Сразу сделать активной
}
```

---

### 4. Описание эндпоинтов

#### 4.1. Список версий

```
GET /api/v1/agents/{agent_id}/system-prompt/history?limit=30&cursor=5
```

**Query-параметры:**
- `limit` (int, default 30, max 100) — количество записей в порции
- `cursor` (int, optional) — `version_number` последнего загруженного элемента. При первом запросе не передаётся.

**Ответ:** `200 OK` — `SystemPromptVersionListResponse`

**Пример первого запроса** (`GET .../history?limit=30`):
```json
{
  "items": [
    {
      "id": "a1b2c3d4-...",
      "agent_id": "176548eb-...",
      "version_number": 3,
      "change_summary": "Публикация агента",
      "triggered_by": "publish",
      "is_active": true,
      "created_by": "user-uuid-...",
      "created_at": "2026-02-09T18:30:00Z",
      "prompt_length": 1247
    },
    {
      "id": "e5f6g7h8-...",
      "agent_id": "176548eb-...",
      "version_number": 2,
      "change_summary": null,
      "triggered_by": "update",
      "is_active": false,
      "created_by": "user-uuid-...",
      "created_at": "2026-02-09T15:00:00Z",
      "prompt_length": 980
    }
  ],
  "next_cursor": null
}
```

- `next_cursor: null` — данных больше нет, кнопку «Загрузить ещё» не показываем.
- `next_cursor: 5` — есть ещё, следующий запрос: `GET .../history?limit=30&cursor=5`.

**Замечание:** В списке **не возвращается** полный текст промпта (`system_prompt`). Вместо него — `prompt_length`. Полный текст запрашивается отдельно через `GET .../history/{version_id}`.

---

#### 4.2. Текущая активная версия

```
GET /api/v1/agents/{agent_id}/system-prompt/current
```

**Ответ:** `200 OK` — `SystemPromptVersionRead`

**Ошибки:**
- `404` — у агента нет ни одной версии (для агентов, созданных до введения этой фичи)

---

#### 4.3. Детали конкретной версии

```
GET /api/v1/agents/{agent_id}/system-prompt/history/{version_id}
```

**Ответ:** `200 OK` — `SystemPromptVersionRead` (включая полный `system_prompt`)

**Ошибки:**
- `404` — версия не найдена

---

#### 4.4. Создать новую версию вручную

```
POST /api/v1/agents/{agent_id}/system-prompt/history
Content-Type: application/json

{
  "system_prompt": "Ты — ассистент стоматологической клиники...",
  "change_summary": "Добавлен блок про акции",
  "activate": true
}
```

**Ответ:** `201 Created` — `SystemPromptVersionRead`

**Поведение:**
- Если `activate: true` (по умолчанию) — все предыдущие версии деактивируются, `agent.system_prompt` обновляется.
- Если `activate: false` — версия сохраняется как черновик, агент продолжает использовать предыдущий промпт.
- Автоматически присваивается следующий `version_number`.

**Ошибки:**
- `404` — агент не найден
- `422` — невалидные данные

---

#### 4.5. Активировать существующую версию

```
POST /api/v1/agents/{agent_id}/system-prompt/history/{version_id}/activate
```

**Ответ:** `200 OK` — `SystemPromptVersionRead` (активированная версия)

**Поведение:**
- Деактивирует текущую активную версию.
- Активирует указанную. Обновляет `agent.system_prompt` и `agent.version`.
- Если версия уже активна — возвращает её без изменений.

**Ошибки:**
- `404` — версия не найдена

---

### 5. Значения поля `triggered_by`

| Значение | Когда создаётся |
|----------|-----------------|
| `create` | При создании агента (`POST /agents`) |
| `update` | При обновлении агента (`PUT /agents/{id}`), если `system_prompt` изменился |
| `publish` | При публикации агента (`POST /agents/{id}/publish`) |
| `manual` | При ручном создании через `POST /system-prompt/history` |

Фронт должен отображать эти значения человекочитаемо:
- `create` → «Создание агента»
- `update` → «Обновление»
- `publish` → «Публикация»
- `manual` → «Ручное изменение»

---

### 6. Логика взаимодействия

#### 6.1. Загрузка раздела истории
1. `GET /system-prompt/history` — первая порция (до 30 записей).
2. Если `next_cursor !== null` — показать «Загрузить ещё».
3. Активная версия помечена `is_active: true` — визуально выделить.

#### 6.2. Просмотр версии
1. Клик по элементу списка → `GET /system-prompt/history/{version_id}`.
2. Показать полный текст `system_prompt` в read-only режиме.
3. Если версия не активна — показать кнопку «Активировать».

#### 6.3. Откат на предыдущую версию
1. Пользователь нажимает «Активировать» на неактивной версии.
2. Показать подтверждение: «Текущий промпт будет заменён на версию #N. Продолжить?»
3. `POST /system-prompt/history/{version_id}/activate`.
4. Обновить список и карточку агента (промпт изменился).

#### 6.4. Создание новой версии
1. Пользователь редактирует текст промпта.
2. Опционально вводит `change_summary`.
3. `POST /system-prompt/history` с `activate: true`.
4. Обновить список.

#### 6.5. Связь с существующим редактором промпта
- При сохранении агента через `PUT /agents/{id}` с изменённым `system_prompt` бэкенд автоматически создаёт версию. Фронту не нужно делать дополнительных запросов.
- После сохранения можно обновить список истории для отображения новой записи.

---

### 7. Обработка ошибок

| Код | Ситуация | Действие на фронте |
|-----|----------|--------------------|
| `404` на `/current` | У агента нет истории (legacy-агент) | Показать заглушку «История промпта пока пуста» |
| `404` на `/history/{id}` | Версия удалена/не существует | Показать toast «Версия не найдена» |
| `404` на `/activate` | Версия не существует | Показать toast «Не удалось активировать» |
| `422` на `POST /history` | Невалидный `system_prompt` | Показать ошибки валидации у полей формы |

---

### 8. Отображение списка

- Первый запрос без `cursor` — загружает последние 30 версий.
- Обычно этого достаточно. Если `next_cursor !== null` — показать кнопку «Загрузить ещё» внизу списка.
- При клике — запросить `GET .../history?limit=30&cursor={next_cursor}`, дописать `items` в конец.
- Повторять, пока `next_cursor` не станет `null`.
- Если `items` пуст — показать заглушку «История промпта пока пуста».
