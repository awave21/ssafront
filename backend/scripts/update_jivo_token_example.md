# Пример использования скрипта update_jivo_token.sql

## Сценарий: обновление токена для канала агента "Клиника Красоты"

### Шаг 1: Поиск текущего канала

Сначала найдем информацию о текущем Jivo канале:

```sql
-- Найти все Jivo каналы с информацией об агентах
SELECT 
    a.id AS agent_id,
    a.name AS agent_name,
    c.id AS channel_id,
    c.jivo_provider_token AS current_token,
    c.jivo_provider_id,
    c.jivo_reply_base_url,
    c.created_at,
    c.updated_at
FROM agents a
JOIN agent_channels ac ON a.id = ac.agent_id
JOIN channels c ON ac.channel_id = c.id
WHERE 
    c.type = 'jivo' 
    AND c.is_deleted = false
    AND a.name ILIKE '%красоты%';
```

**Результат:**
```
agent_id    | 123e4567-e89b-12d3-a456-426614174000
agent_name  | Клиника Красоты - Консультант
channel_id  | 987fcdeb-51a2-43c1-8765-123456789abc
current_token | old-token-abc123xyz456
jivo_provider_id | 12345
jivo_reply_base_url | https://bot.jivosite.com/webhooks
```

### Шаг 2: Генерация нового токена

Используем Python для генерации безопасного токена:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Результат:**
```
X7KzPq9R2mN4vL8cYwQjT5dH6fA3sG1nU0bZ9xE4tM
```

### Шаг 3: Применение скрипта (Вариант 1 - по agent_id)

Создаем файл `update_jivo_token_clinic.sql` с конкретными значениями:

```sql
-- Обновление токена Jivo для агента "Клиника Красоты"
-- Дата: 2026-08-05
-- Причина: Плановая ротация токенов безопасности

BEGIN;

UPDATE channels
SET 
    jivo_provider_token = 'X7KzPq9R2mN4vL8cYwQjT5dH6fA3sG1nU0bZ9xE4tM',
    updated_at = NOW()
WHERE 
    id IN (
        SELECT c.id
        FROM channels c
        JOIN agent_channels ac ON c.id = ac.channel_id
        WHERE 
            ac.agent_id = '123e4567-e89b-12d3-a456-426614174000'::uuid
            AND c.type = 'jivo'
            AND c.is_deleted = false
    )
    AND type = 'jivo'
    AND is_deleted = false;

-- Проверка
DO $$
BEGIN
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Канал не найден';
    END IF;
END $$;

-- Проверка результата
SELECT 
    c.id AS channel_id,
    c.jivo_provider_token,
    c.updated_at,
    a.name AS agent_name
FROM channels c
JOIN agent_channels ac ON c.id = ac.channel_id
JOIN agents a ON ac.agent_id = a.id
WHERE 
    ac.agent_id = '123e4567-e89b-12d3-a456-426614174000'::uuid
    AND c.type = 'jivo';

-- Если всё OK:
COMMIT;
```

### Шаг 4: Выполнение

```bash
# Применяем скрипт
psql -U postgres -d myapp_db -f update_jivo_token_clinic.sql

# Или через Docker, если база в контейнере
docker exec -i postgres_container psql -U postgres -d myapp_db < update_jivo_token_clinic.sql
```

### Шаг 5: Обновление webhook в Jivo

После успешного обновления в БД необходимо обновить webhook URL в настройках Jivo Bot API:

**Старый URL:**
```
https://api.yourdomain.com/api/v1/webhooks/jivo/old-token-abc123xyz456
```

**Новый URL:**
```
https://api.yourdomain.com/api/v1/webhooks/jivo/X7KzPq9R2mN4vL8cYwQjT5dH6fA3sG1nU0bZ9xE4tM
```

**Шаги в Jivo:**
1. Войдите в личный кабинет Jivo
2. Перейдите в раздел "Управление" → "Каналы" → "Bot API"
3. Найдите подключение для вашего канала
4. Обновите Webhook URL на новый
5. Сохраните изменения

### Шаг 6: Тестирование

Проверьте работоспособность канала:

```bash
# 1. Отправьте тестовое сообщение через Jivo
# 2. Проверьте логи приложения на наличие входящих webhook'ов

# В логах должна появиться запись:
# "Received Jivo webhook for channel 987fcdeb-51a2-43c1-8765-123456789abc"

# 3. Проверьте, что бот отвечает на сообщения
```

### Альтернативный вариант: обновление по старому токену

Если вы знаете старый токен, можно использовать более простой вариант:

```sql
BEGIN;

UPDATE channels
SET 
    jivo_provider_token = 'X7KzPq9R2mN4vL8cYwQjT5dH6fA3sG1nU0bZ9xE4tM',
    updated_at = NOW()
WHERE 
    jivo_provider_token = 'old-token-abc123xyz456'
    AND type = 'jivo'
    AND is_deleted = false;

SELECT 
    id, 
    jivo_provider_token, 
    updated_at
FROM channels
WHERE jivo_provider_token = 'X7KzPq9R2mN4vL8cYwQjT5dH6fA3sG1nU0bZ9xE4tM';

COMMIT;
```

## Возможные проблемы и решения

### Ошибка: "duplicate key value violates unique constraint"

**Причина:** новый токен уже используется другим каналом (токены должны быть уникальными)

**Решение:** сгенерируйте другой токен

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Ошибка: "Канал не найден"

**Причина:** неправильный agent_id, channel_id или канал удален

**Решение:** проверьте ID через SELECT запрос из Шага 1

### Webhook не работает после обновления

**Причина:** не обновили URL в настройках Jivo или опечатка в токене

**Решение:**
1. Проверьте токен в БД
2. Убедитесь, что URL в Jivo точно соответствует новому токену
3. Проверьте логи сервера на наличие ошибок 401 Unauthorized

## Чек-лист обновления токена

- [ ] Найден текущий канал и его параметры
- [ ] Сгенерирован новый уникальный токен
- [ ] Создан SQL скрипт с конкретными значениями
- [ ] Выполнен скрипт в транзакции
- [ ] Проверен результат SELECT запросом
- [ ] Сделан COMMIT транзакции
- [ ] Обновлен webhook URL в настройках Jivo
- [ ] Проведено тестирование (отправка/получение сообщений)
- [ ] Обновлена документация (если токен хранится где-то еще)
- [ ] Старый токен удален из конфигов и секретов

## Автоматизация (опционально)

Можно создать Python скрипт для автоматизации процесса:

```python
# backend/scripts/rotate_jivo_token.py
import secrets
import sys
from sqlalchemy import text
from app.db.session import SessionLocal

def rotate_jivo_token(agent_id: str) -> tuple[str, str]:
    """Ротация токена Jivo для указанного агента"""
    
    # Генерируем новый токен
    new_token = secrets.token_urlsafe(32)
    
    db = SessionLocal()
    try:
        # Обновляем токен
        result = db.execute(
            text("""
                UPDATE channels
                SET jivo_provider_token = :new_token, updated_at = NOW()
                WHERE id IN (
                    SELECT c.id FROM channels c
                    JOIN agent_channels ac ON c.id = ac.channel_id
                    WHERE ac.agent_id = :agent_id
                    AND c.type = 'jivo' AND c.is_deleted = false
                )
                RETURNING id, jivo_provider_token
            """),
            {"agent_id": agent_id, "new_token": new_token}
        )
        
        row = result.fetchone()
        if not row:
            raise ValueError(f"Jivo канал для агента {agent_id} не найден")
        
        db.commit()
        
        channel_id, token = row
        return str(channel_id), token
        
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rotate_jivo_token.py <agent_id>")
        sys.exit(1)
    
    agent_id = sys.argv[1]
    channel_id, new_token = rotate_jivo_token(agent_id)
    
    print(f"✓ Токен успешно обновлен")
    print(f"Channel ID: {channel_id}")
    print(f"Новый токен: {new_token}")
    print(f"\nНовый webhook URL:")
    print(f"https://your-domain/api/v1/webhooks/jivo/{new_token}")
```

Использование:

```bash
cd backend
python scripts/rotate_jivo_token.py 123e4567-e89b-12d3-a456-426614174000
```
