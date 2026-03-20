# Спецификация: Роли и Scopes для бэкенда

## Проблема

Текущий бэкенд возвращает только `tools:read`, `tools:write` в поле `scopes`, но фронтенд ожидает расширенный набор прав для управления UI-функциями.

## Требуемые изменения

### 1. Добавить маппинг ролей на scopes

Создать константу с правами для каждой роли:

```python
# app/core/permissions.py (или в существующем файле конфигурации)

ROLE_SCOPES = {
    "owner": [
        # Агенты
        "agents:read",
        "agents:write",
        # Участники организации
        "members:manage",
        # Диалоги
        "dialogs:read",
        "dialogs:write",
        "dialogs:delete",
        # Аналитика
        "analytics:view",
        # Организация
        "organization:manage",
        # Инструменты (существующие)
        "tools:read",
        "tools:write",
    ],
    "admin": [
        "agents:read",
        "agents:write",
        "members:manage",
        "dialogs:read",
        "dialogs:write",
        "dialogs:delete",
        "analytics:view",
        "organization:manage",
        "tools:read",
        "tools:write",
    ],
    "manager": [
        "agents:read",
        "dialogs:read",
        "dialogs:write",
        "analytics:view",
        "tools:read",
    ],
}

def get_scopes_for_role(role: str) -> list[str]:
    """Возвращает список scopes для указанной роли."""
    return ROLE_SCOPES.get(role, [])
```

### 2. Обновить эндпоинт `/auth/me`

При возврате данных пользователя — добавлять scopes на основе роли:

```python
# В роутере auth (app/api/routers/auth.py)

from app.core.permissions import get_scopes_for_role

@router.get("/me")
async def get_current_user(current_user: User = Depends(get_current_user)):
    # Получаем scopes на основе роли пользователя
    scopes = get_scopes_for_role(current_user.role)
    
    return {
        "user": {
            "id": str(current_user.id),
            "tenant_id": str(current_user.tenant_id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "scopes": scopes,  # <-- Scopes на основе роли
            "is_active": current_user.is_active,
            "last_login_at": current_user.last_login_at,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at,
        },
        "tenant": {
            "id": str(current_user.tenant.id),
            "name": current_user.tenant.name,
            "is_active": current_user.tenant.is_active,
            "created_at": current_user.tenant.created_at,
            "updated_at": current_user.tenant.updated_at,
        }
    }
```

### 3. Обновить генерацию JWT токена

При создании токена — включать scopes в claims:

```python
# В security.py или там, где создаётся JWT

from app.core.permissions import get_scopes_for_role

def create_access_token(user: User, expires_delta: timedelta | None = None) -> str:
    scopes = get_scopes_for_role(user.role)
    
    payload = {
        "sub": str(user.id),
        "tenant_id": str(user.tenant_id),
        "scopes": scopes,  # <-- Scopes на основе роли
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "exp": datetime.utcnow() + (expires_delta or timedelta(minutes=30)),
        "iat": datetime.utcnow(),
    }
    
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
```

### 4. Обновить `/auth/login` и `/auth/register`

Аналогично `/auth/me` — возвращать scopes на основе роли в ответе:

```python
@router.post("/login")
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, credentials.email, credentials.password)
    
    # ... существующая логика ...
    
    scopes = get_scopes_for_role(user.role)
    
    return {
        "token": access_token,
        "refresh_token": refresh_token,
        "user": {
            # ... другие поля ...
            "role": user.role,
            "scopes": scopes,  # <-- Добавить
        },
        "tenant": { ... }
    }
```

## Описание scopes

| Scope | Описание |
|-------|----------|
| `agents:read` | Просмотр списка агентов |
| `agents:write` | Создание, редактирование, удаление агентов |
| `members:manage` | Управление участниками организации (приглашение, изменение ролей, удаление) |
| `dialogs:read` | Просмотр диалогов |
| `dialogs:write` | Отправка сообщений в диалогах |
| `dialogs:delete` | Удаление диалогов |
| `analytics:view` | Просмотр аналитики |
| `organization:manage` | Управление настройками организации |
| `tools:read` | Просмотр инструментов |
| `tools:write` | Создание и редактирование инструментов |

## Матрица ролей

| Scope | Owner | Admin | Manager |
|-------|:-----:|:-----:|:-------:|
| `agents:read` | ✅ | ✅ | ✅ |
| `agents:write` | ✅ | ✅ | ❌ |
| `members:manage` | ✅ | ✅ | ❌ |
| `dialogs:read` | ✅ | ✅ | ✅ |
| `dialogs:write` | ✅ | ✅ | ✅ |
| `dialogs:delete` | ✅ | ✅ | ❌ |
| `analytics:view` | ✅ | ✅ | ✅ |
| `organization:manage` | ✅ | ✅ | ❌ |
| `tools:read` | ✅ | ✅ | ✅ |
| `tools:write` | ✅ | ✅ | ❌ |

## Тестирование

После внесения изменений проверить:

1. **Логин owner** — должен получить все scopes
2. **Логин admin** — должен получить все scopes кроме специфичных для owner (если такие будут)
3. **Логин manager** — должен получить ограниченный набор scopes
4. **JWT токен** — декодировать и проверить наличие правильных scopes
5. **Фронтенд** — страница `/settings/team` должна быть доступна для owner и admin

## Временное решение на фронтенде

Пока бэкенд не обновлён, на фронтенде применён фикс: права определяются по роли пользователя, а scopes с бэкенда используются как дополнение. Файл: `composables/usePermissions.ts`.

После обновления бэкенда можно убрать отладочные логи из `usePermissions.ts`.
