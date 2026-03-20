# Ролевая система и приглашения — фронтендовая спецификация

## 1. Обзор

Реализована ролевая система на уровне организации (tenant): роли **owner**, **admin**, **manager**. Владелец (owner) может приглашать пользователей по email. Приглашённый получает ссылку для присоединения к организации.

### Роли

| Роль | Описание |
|------|----------|
| owner | Владелец организации, полный доступ |
| admin | Все права, кроме удаления владельца |
| manager | Просмотр агентов, диалоги (создание, сообщения), без редактирования агентов и управления участниками |

## 2. Данные для UI

### Текущий пользователь (GET /auth/me)

В ответе `UserRead` приходят `role` и `scopes`. Использовать для условного отображения элементов.

```json
{
  "user": {
    "id": "uuid",
    "tenant_id": "uuid",
    "email": "...",
    "full_name": "...",
    "role": "owner",
    "scopes": ["agents:read", "agents:write", ...],
    "is_active": true,
    ...
  },
  "tenant": { ... }
}
```

### Composable `usePermissions()`

Рекомендуется создать composable для проверки прав:

```ts
// Пример
const { canEditAgents, canManageMembers, canViewAnalytics } = usePermissions()

// canEditAgents = role in ['owner', 'admin']
// canManageMembers = role in ['owner', 'admin']
// canViewAnalytics = true (все роли)
```

## 3. Страница «Участники» (/settings/team или /organization/members)

**Видимость:** owner, admin (не показывать для manager)

**Элементы:**
- Таблица: email, имя, роль, дата входа, действия
- Для владельца — бейдж «Владелец», без кнопки удаления
- Кнопка «Пригласить» → модалка

**API:**
- `GET /users` — список участников
- `PATCH /users/{user_id}/role` — смена роли, body: `{ "role": "admin" | "manager" }`
- `DELETE /users/{user_id}` — удаление участника

## 4. Модалка «Пригласить пользователя»

**Поля:**
- Email (обязательный)
- Роль: Admin / Manager (dropdown)

**API:** `POST /invitations`

Request:
```json
{
  "email": "user@example.com",
  "role": "admin"
}
```

Response:
```json
{
  "id": "uuid",
  "email": "...",
  "role": "...",
  "expires_at": "2026-02-12T...",
  "invited_by_user_id": "uuid",
  "created_at": "...",
  "invite_link": "https://app.example.com/invite/accept?token=..."
}
```

**После создания:** Показать скопируемую ссылку `invite_link` и кнопку «Копировать». Email не отправляется.

## 5. Страница «Принять приглашение» (/invite/accept?token=...)

**Путь:** Публичная страница (без авторизации).

**Элементы:**
- Если token невалиден/истёк — сообщение об ошибке
- Форма: пароль, подтверждение пароля, имя (опционально)
- Кнопка «Присоединиться»

**API:** `POST /invitations/accept` или `POST /auth/register-by-invite`

Request:
```json
{
  "token": "invite_token_from_url",
  "password": "min 8 chars",
  "full_name": "Имя (опционально)"
}
```

Response: `AuthTokenResponse` (token, refresh_token, user, tenant)

**После успеха:** Редирект в приложение (или на /dashboard).

## 6. Условное отображение по ролям

| Элемент | owner | admin | manager |
|---------|-------|-------|---------|
| Список агентов | + | + | + |
| Кнопки создания/редактирования/удаления агента | + | + | - |
| Карточка агента: SQNS, каналы, инструменты | + | + | - |
| Диалоги: просмотр | + | + | + |
| Диалоги: создание, отправка сообщений | + | + | + |
| Диалоги: удаление | + | + | - |
| Аналитика | + | + | + |
| Раздел «Участники» | + | + | - |
| Настройки организации | + | + | - |

## 7. Обработка 403

При ответе 403 (Forbidden) показывать сообщение «Недостаточно прав» вместо общей ошибки.
