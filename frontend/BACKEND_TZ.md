# Техническое задание: Реализация аутентификации и авторизации на бэкенде

## 1. Общие требования

### 1.1. Цель
Реализовать систему аутентификации и авторизации с использованием JWT токенов для фронтенда, который уже реализован и ожидает следующие эндпоинты.

### 1.2. Технологии
- Python (FastAPI рекомендуется, или существующий фреймворк)
- JWT для токенов (PyJWT)
- bcrypt или argon2 для хеширования паролей
- PostgreSQL для хранения данных
- Redis для rate limiting и blacklist токенов (опционально)

---

## 2. Эндпоинты аутентификации

### 2.1. `POST /api/v1/auth/register` - Регистрация нового пользователя

#### 2.1.1. Описание
Создает нового пользователя, создает или привязывает к tenant, генерирует JWT токен.

#### 2.1.2. Запрос (Request)

**URL:** `POST /api/v1/auth/register`

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "full_name": "Иван Иванов",
  "tenant_name": "Моя Компания"
}
```

**Схема валидации:**
```python
{
  "email": str,          # Обязательно, валидный email, уникальный, max 255 символов
  "password": str,       # Обязательно, минимум 8 символов, max 128 символов
  "full_name": str,      # Опционально, max 200 символов
  "tenant_name": str     # Опционально, max 200 символов
}
```

#### 2.1.3. Валидация на бэкенде

**Email:**
- Обязательное поле
- Формат: `^[^\s@]+@[^\s@]+\.[^\s@]+$`
- Уникальность в базе данных (проверка перед созданием)
- Максимум 255 символов
- Приведение к lowercase

**Password:**
- Обязательное поле
- Минимум 8 символов
- Максимум 128 символов
- Рекомендуется проверка сложности (но не обязательно):
  - Заглавные буквы
  - Строчные буквы
  - Цифры
  - Специальные символы

**full_name:**
- Опциональное поле
- Максимум 200 символов
- Если не указано, используется email

**tenant_name:**
- Опциональное поле
- Максимум 200 символов
- Если не указано, генерируется автоматически: `"Организация {email}"`

#### 2.1.4. Логика работы

1. **Валидация входных данных**
   - Проверка формата email
   - Проверка длины пароля
   - Проверка уникальности email

2. **Создание пользователя**
   - Хеширование пароля (bcrypt с cost=12+ или argon2)
   - Создание записи в таблице `users`
   - Установка роли `owner` (первый пользователь в tenant)

3. **Создание/получение tenant**
   - Если `tenant_name` указан:
     - Проверка существования tenant с таким именем
     - Если не существует - создать новый
     - Если существует - привязать пользователя к существующему
   - Если `tenant_name` не указан:
     - Создать новый tenant с автоматическим именем

4. **Генерация JWT токена**
   - Создать access token с claims (см. раздел 3)
   - Время жизни: 15 минут (настраивается через `JWT_ACCESS_TOKEN_EXPIRES_IN`)

5. **Возврат ответа**
   - Токен
   - Данные пользователя
   - Данные tenant

#### 2.1.5. Ответ (Response)

**Успех (200 OK):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwidGVuYW50X2lkIjoiMTIzNDU2Nzg5MCIsInNjb3BlcyI6WyJ0b29sczpyZWFkIiwidG9vbHM6d3JpdGUiXSwiZXhwIjoxNTE2MjM5MDIyfQ...",
  "user": {
    "id": "00000000-0000-0000-0000-000000000001",
    "tenant_id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "full_name": "Иван Иванов",
    "role": "owner",
    "scopes": ["tools:read", "tools:write"],
    "is_active": true,
    "last_login_at": null,
    "created_at": "2024-01-27T10:00:00Z",
    "updated_at": null
  },
  "tenant": {
    "id": "00000000-0000-0000-0000-000000000002",
    "name": "Моя Компания",
    "is_active": true,
    "created_at": "2024-01-27T10:00:00Z",
    "updated_at": null
  }
}
```

**Ошибки:**

**400 Bad Request - Валидация не прошла:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "details": {
    "email": ["Invalid email format"],
    "password": ["Password must be at least 8 characters"]
  }
}
```

**409 Conflict - Email уже существует:**
```json
{
  "error": "email_exists",
  "message": "User with this email already exists"
}
```

**500 Internal Server Error:**
```json
{
  "error": "internal_error",
  "message": "Internal server error"
}
```

---

### 2.2. `POST /api/v1/auth/login` - Вход пользователя

#### 2.2.1. Описание
Аутентифицирует пользователя по email и паролю, возвращает JWT токен.

#### 2.2.2. Запрос (Request)

**URL:** `POST /api/v1/auth/login`

**Headers:**
```
Content-Type: application/json
```

**Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Схема валидации:**
```python
{
  "email": str,    # Обязательно, валидный email
  "password": str  # Обязательно, минимум 8 символов
}
```

#### 2.2.3. Валидация на бэкенде

**Email:**
- Обязательное поле
- Формат email
- Приведение к lowercase

**Password:**
- Обязательное поле
- Минимум 8 символов

#### 2.2.4. Логика работы

1. **Валидация входных данных**
   - Проверка формата email
   - Проверка наличия пароля

2. **Поиск пользователя**
   - Поиск по email (case-insensitive)
   - Проверка существования пользователя

3. **Проверка пароля**
   - Сравнение хеша пароля с сохраненным (constant-time сравнение)
   - Защита от timing attacks

4. **Проверка активности аккаунта**
   - Проверка `is_active = true`
   - Если неактивен - вернуть 403

5. **Обновление last_login_at**
   - Установить текущее время в `last_login_at`

6. **Генерация JWT токена**
   - Создать access token с claims
   - Время жизни: 15 минут

7. **Логирование**
   - Записать успешную попытку входа (IP, user agent, timestamp)

8. **Возврат ответа**
   - Токен
   - Данные пользователя
   - Данные tenant

#### 2.2.5. Ответ (Response)

**Успех (200 OK):**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "00000000-0000-0000-0000-000000000001",
    "tenant_id": "00000000-0000-0000-0000-000000000002",
    "email": "user@example.com",
    "full_name": "Иван Иванов",
    "role": "owner",
    "scopes": ["tools:read", "tools:write"],
    "is_active": true,
    "last_login_at": "2024-01-27T10:00:00Z",
    "created_at": "2024-01-20T10:00:00Z",
    "updated_at": "2024-01-27T10:00:00Z"
  },
  "tenant": {
    "id": "00000000-0000-0000-0000-000000000002",
    "name": "Моя Компания",
    "is_active": true,
    "created_at": "2024-01-20T10:00:00Z",
    "updated_at": null
  }
}
```

**Ошибки:**

**400 Bad Request - Валидация не прошла:**
```json
{
  "error": "validation_error",
  "message": "Validation failed",
  "details": {
    "email": ["Invalid email format"],
    "password": ["Password is required"]
  }
}
```

**401 Unauthorized - Неверные credentials:**
```json
{
  "error": "invalid_credentials",
  "message": "Invalid email or password"
}
```

**403 Forbidden - Аккаунт неактивен:**
```json
{
  "error": "account_inactive",
  "message": "Account is inactive"
}
```

**429 Too Many Requests - Rate limit превышен:**
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many login attempts. Please try again later.",
  "retry_after": 60
}
```

---

## 3. JWT токены

### 3.1. Структура JWT токена

**Claims в токене:**
```json
{
  "sub": "00000000-0000-0000-0000-000000000001",  // user_id (subject)
  "tenant_id": "00000000-0000-0000-0000-000000000002",
  "scopes": ["tools:read", "tools:write"],
  "iss": "agent-platform",                        // issuer
  "aud": "agent-platform",                        // audience
  "exp": 1706356822,                              // expiration (Unix timestamp в секундах)
  "iat": 1706356222,                              // issued at (Unix timestamp в секундах)
  "jti": "550e8400-e29b-41d4-a716-446655440000"  // JWT ID (для отзыва)
}
```

### 3.2. Настройки JWT

**Переменные окружения:**
```bash
JWT_SECRET=your-secret-key                    # Секретный ключ для подписи
JWT_ALGORITHM=HS256                          # Алгоритм подписи
JWT_AUDIENCE=agent-platform                  # Audience claim
JWT_ISSUER=agent-platform                    # Issuer claim
JWT_ACCESS_TOKEN_EXPIRES_IN=15m             # Время жизни access token (15 минут)
```

### 3.3. Генерация токена

**Пример кода (Python):**
```python
import jwt
from datetime import datetime, timedelta
import uuid

def create_access_token(user_id: str, tenant_id: str, scopes: list[str]) -> str:
    now = datetime.utcnow()
    expires_in = timedelta(minutes=15)  # Из переменной окружения
    
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "scopes": scopes,
        "iss": os.getenv("JWT_ISSUER", "agent-platform"),
        "aud": os.getenv("JWT_AUDIENCE", "agent-platform"),
        "exp": int((now + expires_in).timestamp()),
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4())  # Для возможности отзыва
    }
    
    token = jwt.encode(
        payload,
        os.getenv("JWT_SECRET"),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256")
    )
    
    return token
```

### 3.4. Валидация токена

**При каждом запросе:**
1. Проверить наличие токена в заголовке `Authorization: Bearer <token>`
2. Декодировать и проверить подпись
3. Проверить `exp` (срок действия)
4. Проверить `iss` и `aud`
5. Проверить blacklist (если реализован отзыв токенов)
6. Извлечь `sub` (user_id) и `tenant_id` для дальнейшей авторизации

---

## 4. Безопасность паролей

### 4.1. Хеширование паролей

**Требования:**
- Использовать bcrypt с cost=12+ или argon2
- Никогда не хранить пароли в открытом виде
- Использовать salt (автоматически в bcrypt/argon2)

**Пример (Python с bcrypt):**
```python
import bcrypt

def hash_password(password: str) -> str:
    # Генерация salt и хеширование
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    # Constant-time сравнение для защиты от timing attacks
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
```

### 4.2. Защита от timing attacks

- Использовать constant-time функции сравнения
- Не раскрывать, существует ли пользователь с таким email (при неверном пароле)

---

## 5. Rate Limiting

### 5.1. Настройки

**Переменные окружения:**
```bash
RATE_LIMIT_AUTH_LOGIN=5/minute      # 5 попыток входа в минуту
RATE_LIMIT_AUTH_REGISTER=3/hour     # 3 регистрации в час
RATE_LIMIT_AUTH_REFRESH=10/minute   # 10 обновлений токена в минуту
```

### 5.2. Реализация

**Для `/auth/login`:**
- Лимит: 5 запросов в минуту на IP
- При превышении: HTTP 429
- Заголовок ответа: `Retry-After: 60`

**Для `/auth/register`:**
- Лимит: 3 запроса в час на IP
- При превышении: HTTP 429
- Заголовок ответа: `Retry-After: 3600`

**Хранение состояния:**
- Redis (рекомендуется)
- Или in-memory (для простых случаев)

**Пример заголовков ответа при 429:**
```
HTTP/1.1 429 Too Many Requests
Retry-After: 60
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1640000000
```

---

## 6. Логирование

### 6.1. Что логировать

**Успешные входы:**
- user_id
- email
- IP адрес
- User-Agent
- Timestamp

**Неудачные попытки входа:**
- email (если валидный)
- IP адрес
- User-Agent
- Причина (invalid_credentials, account_inactive, validation_error)
- Timestamp

**Регистрации:**
- user_id
- email
- IP адрес
- Timestamp

### 6.2. Формат логов

**Рекомендуемый формат (JSON):**
```json
{
  "event": "login_success",
  "user_id": "00000000-0000-0000-0000-000000000001",
  "email": "user@example.com",
  "ip": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "timestamp": "2024-01-27T10:00:00Z"
}
```

---

## 7. Структура базы данных

### 7.1. Таблица `users`

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200),
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    scopes TEXT[] DEFAULT ARRAY[]::TEXT[],
    is_active BOOLEAN NOT NULL DEFAULT true,
    last_login_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT users_email_lowercase CHECK (email = LOWER(email))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
```

### 7.2. Таблица `tenants`

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_tenants_name ON tenants(name);
```

### 7.3. Таблица `token_blacklist` (опционально, для отзыва токенов)

```sql
CREATE TABLE token_blacklist (
    jti VARCHAR(255) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_token_blacklist_expires_at ON token_blacklist(expires_at);
```

---

## 8. Обработка ошибок

### 8.1. Стандартизация ошибок

**Формат ошибки:**
```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "details": {
    "field_name": ["error message 1", "error message 2"]
  }
}
```

### 8.2. Коды ошибок

- `validation_error` - Ошибка валидации входных данных
- `email_exists` - Email уже существует
- `invalid_credentials` - Неверный email или пароль
- `account_inactive` - Аккаунт неактивен
- `rate_limit_exceeded` - Превышен лимит запросов
- `token_expired` - Токен истек
- `token_invalid` - Токен невалиден
- `internal_error` - Внутренняя ошибка сервера

---

## 9. Дополнительные требования

### 9.1. Производительность

- Время ответа для `/auth/login` и `/auth/register`: < 500ms
- Использовать индексы в БД
- Кэширование при необходимости

### 9.2. Безопасность

- HTTPS обязательно в production
- Защита от SQL injection (использовать ORM или prepared statements)
- Защита от XSS (валидация входных данных)
- CORS настройки для фронтенда
- Защита от CSRF (если используются cookies)

### 9.3. Тестирование

**Обязательные тесты:**
- Успешная регистрация
- Успешный вход
- Валидация email
- Валидация пароля
- Проверка уникальности email
- Проверка rate limiting
- Проверка истечения токена
- Проверка неактивного аккаунта

---

## 10. Примеры использования

### 10.1. Регистрация

```bash
curl -X POST https://agentsapp.integration-ai.ru/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "password": "SecurePassword123!",
    "full_name": "Новый Пользователь",
    "tenant_name": "Новая Компания"
  }'
```

### 10.2. Вход

```bash
curl -X POST https://agentsapp.integration-ai.ru/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }'
```

### 10.3. Использование токена

```bash
curl -X GET https://agentsapp.integration-ai.ru/api/v1/agents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## 11. Приоритет реализации

### Критично (сделать сразу):
1. ✅ `POST /auth/register` - Регистрация
2. ✅ `POST /auth/login` - Вход
3. ✅ JWT токены с временем жизни (exp)
4. ✅ Валидация входных данных
5. ✅ Хеширование паролей (bcrypt/argon2)
6. ✅ Обработка ошибок в стандартном формате

### Важно (сделать в ближайшее время):
7. ✅ Rate limiting для auth эндпоинтов
8. ✅ Логирование попыток входа
9. ✅ Проверка активности аккаунта
10. ✅ Обновление last_login_at

### Рекомендуется (для повышения безопасности):
11. ⚠️ Refresh токены (опционально)
12. ⚠️ Blacklist для отозванных токенов
13. ⚠️ Email верификация (опционально)
14. ⚠️ 2FA (опционально)

---

## 12. Чеклист перед деплоем

- [ ] Все эндпоинты реализованы и протестированы
- [ ] JWT токены генерируются с правильными claims
- [ ] Пароли хешируются безопасно
- [ ] Rate limiting настроен и работает
- [ ] Валидация входных данных работает
- [ ] Обработка ошибок стандартизирована
- [ ] Логирование настроено
- [ ] Тесты написаны и проходят
- [ ] Документация обновлена
- [ ] Переменные окружения настроены
- [ ] HTTPS настроен в production
- [ ] CORS настроен для фронтенда

---

## 13. Контакты и вопросы

При возникновении вопросов по реализации обращаться к команде разработки фронтенда или к техническому лиду проекта.
