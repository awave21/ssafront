# Схема: включение SQNS по email и паролю

## Куда передавать

| Поле | Куда |
|------|------|
| **Метод** | `POST` |
| **URL** | `{BASE}/api/v1/agents/{agent_id}/sqns/enable-by-password` |
| **Заголовки** | `Content-Type: application/json`<br>`Authorization: Bearer <ваш JWT или API-ключ платформы>` |
| **Тело** | JSON, см. ниже |

`{BASE}` — базовый URL бэкенда (например `https://your-api.example.com` или `http://localhost:8000`).

`{agent_id}` — UUID агента (например `de1fc6a9-231b-4622-90a1-404bd7c778ca`).

---

## Схема тела запроса (JSON)

```ts
{
  host: string;           // обязательно, min 1 символ
  email: string;         // обязательно, min 1 символ
  password: string;       // обязательно, min 1 символ
  defaultResourceId?: number;  // опционально
}
```

### Поля

| Поле | Тип | Обязательно | Описание |
|------|-----|-------------|----------|
| `host` | `string` | да | Хост SQNS: `crmexchange.1denta.ru` или `https://crmexchange.1denta.ru`. Бэкенд сам подставит `https://`, если схемы нет. |
| `email` | `string` | да | Email для входа в SQNS. |
| `password` | `string` | да | Пароль. На фронте после отправки очищайте поле, не сохраняйте. |
| `defaultResourceId` | `number` \| `undefined` | нет | Идентификатор ресурса по умолчанию. Если передан — уходит в SQNS при логине и сохраняется в credential. |

---

## Пример запроса

```http
POST /api/v1/agents/de1fc6a9-231b-4622-90a1-404bd7c778ca/sqns/enable-by-password
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

{
  "host": "crmexchange.1denta.ru",
  "email": "user@example.com",
  "password": "user_password",
  "defaultResourceId": 123
}
```

Без `defaultResourceId`:

```json
{
  "host": "crmexchange.1denta.ru",
  "email": "user@example.com",
  "password": "user_password"
}
```

---

## Ответ

- **200** — успех, в теле объект агента (в т.ч. `sqns_enabled: true`, `sqns_configured: true`, `sqns_status: "ok"`, `sqns_host`, `sqns_error: null` и т.д.).
- **400** — неверное тело (например пустой `host`).
- **401** — нет или неверный `Authorization`.
- **404** — агент не найден или удалён.
- **502** — ошибка SQNS (неверный логин/пароль, хост недоступен и т.п.). В `detail` — текст от бэкенда.

---

## Что делает бэкенд

1. Нормализует `host` (добавляет `https://`, если нужно).
2. Отправляет `POST https://{host}/api/v2/auth` с телом:
   ```json
   { "email": "...", "password": "...", "defaultResourceId": 123 }
   ```
   (`defaultResourceId` только если передан в запросе.)
3. Ожидает ответ в виде массива: `[{ "status": "success", "token": "...", "user": {...} }]`, берёт `token` из первого элемента.
4. Проверяет токен вызовом `GET /api/v2/resource`.
5. Сохраняет в БД credential с `{ "value": "<токен>", "direct_bearer": true, "default_resource_id": 123 }` и обновляет агента (`sqns_enabled`, `sqns_configured`, `sqns_host`, `sqns_credential_id` и т.д.).

Пароль и email в БД не хранятся, только полученный `token`.
