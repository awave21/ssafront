# ТЗ: Миграция фронтенда с SSE на WebSocket

## Цель
Перевести real-time коммуникацию с агентами с Server-Sent Events (SSE) на WebSocket для двунаправленной связи.

---

## Что изменилось

### Было (SSE)
```
GET  /api/v1/agents/{agent_id}/events         → получение событий (односторонний канал)
POST /api/v1/agents/{agent_id}/dialogs/{id}/messages/stream → стриминг ответа агента
POST /api/v1/runs/stream                      → стриминг выполнения
```

### Стало (WebSocket)
```
WS /api/v1/agents/{agent_id}/ws?token=JWT     → единый двунаправленный канал
```

**Один WebSocket заменяет все SSE эндпоинты + HTTP запросы на отправку сообщений.**

---

## Задачи для фронтенда

### 1. Подключение к WebSocket

**Было:**
```javascript
const eventSource = new EventSource(`/api/v1/agents/${agentId}/events`, {
  headers: { Authorization: `Bearer ${token}` }
});
```

**Стало:**
```javascript
const ws = new WebSocket(
  `wss://${host}/api/v1/agents/${agentId}/ws?token=${token}`
);
```

> ⚠️ **Важно:** JWT токен передаётся через query-параметр `token`, не через заголовок.

---

### 2. Обработка входящих событий

**Было (SSE):**
```javascript
eventSource.addEventListener('message_created', (e) => {
  const data = JSON.parse(e.data);
  // ...
});
```

**Стало (WebSocket):**
```javascript
ws.onmessage = (event) => {
  const { type, data } = JSON.parse(event.data);
  
  switch (type) {
    case 'message_created':
      // Новое сообщение в диалоге
      break;
    case 'dialog_updated':
      // Обновление списка диалогов
      break;
    case 'run_start':
      // Агент начал обработку
      break;
    case 'run_result':
      // Агент завершил, есть ответ
      break;
    case 'run_error':
      // Ошибка выполнения агента
      break;
    case 'ping':
      // Keep-alive, нужно ответить pong
      ws.send(JSON.stringify({ type: 'pong' }));
      break;
    case 'error':
      // Ошибка обработки запроса
      break;
  }
};
```

---

### 3. Отправка сообщений

**Было (HTTP POST):**
```javascript
await fetch(`/api/v1/agents/${agentId}/dialogs/${dialogId}/messages`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ content: 'Привет!' })
});
```

**Стало (через WebSocket):**
```javascript
ws.send(JSON.stringify({
  type: 'send_message',
  dialog_id: dialogId,
  content: 'Привет!'
}));
```

Ответ придёт асинхронно через события `run_start` → `run_result` или `run_error`.

---

### 4. Подписка на конкретный диалог (опционально)

Для фильтрации событий на клиенте:

```javascript
// Подписаться
ws.send(JSON.stringify({
  type: 'join_dialog',
  dialog_id: 'telegram:123456'
}));

// Отписаться
ws.send(JSON.stringify({
  type: 'leave_dialog',
  dialog_id: 'telegram:123456'
}));
```

---

### 5. Обработка переподключения

WebSocket не имеет встроенного авто-переподключения (в отличие от SSE). Нужно реализовать:

```javascript
class AgentWebSocket {
  constructor(agentId, token) {
    this.agentId = agentId;
    this.token = token;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 1000;
    this.connect();
  }

  connect() {
    this.ws = new WebSocket(
      `wss://${location.host}/api/v1/agents/${this.agentId}/ws?token=${this.token}`
    );

    this.ws.onopen = () => {
      console.log('WebSocket connected');
      this.reconnectAttempts = 0;
    };

    this.ws.onclose = (event) => {
      if (event.code !== 1000) { // Не нормальное закрытие
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    this.ws.onmessage = (event) => {
      this.handleMessage(JSON.parse(event.data));
    };
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached');
      return;
    }

    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;
    
    console.log(`Reconnecting in ${delay}ms...`);
    setTimeout(() => this.connect(), delay);
  }

  handleMessage(message) {
    // Обработка событий
  }

  send(data) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  close() {
    this.ws.close(1000, 'Client closed');
  }
}
```

---

## Формат событий

### Входящие (от клиента к серверу)

| type | Параметры | Описание |
|------|-----------|----------|
| `send_message` | `dialog_id`, `content` | Отправить сообщение и запустить агента |
| `join_dialog` | `dialog_id` | Подписаться на диалог |
| `leave_dialog` | `dialog_id` | Отписаться от диалога |
| `get_status` | — | Запросить статус соединения |
| `pong` | — | Ответ на ping |

### Исходящие (от сервера к клиенту)

| type | Данные | Описание |
|------|--------|----------|
| `message_created` | `id`, `session_id`, `agent_id`, `role`, `content`, `created_at`, `user_info` | Новое сообщение |
| `dialog_updated` | `id`, `agent_id`, `title`, `last_message_preview`, `last_message_at`, `is_new` | Обновление диалога |
| `run_start` | `run_id`, `trace_id`, `dialog_id` | Начало выполнения агента |
| `run_result` | `run_id`, `output`, `dialog_id`, `tokens`, `tools_called` | Результат агента |
| `run_error` | `run_id`, `error`, `dialog_id` | Ошибка выполнения |
| `ping` | `timestamp` | Keep-alive (ответить `pong`) |
| `error` | `message` | Ошибка обработки запроса |
| `status` | `connected`, `agent_id`, `connections_count` | Статус соединения |
| `dialog_joined` | `dialog_id` | Подтверждение подписки |
| `dialog_left` | `dialog_id` | Подтверждение отписки |

---

## Чеклист миграции

- [ ] Заменить `EventSource` на `WebSocket`
- [ ] Передавать токен через query-параметр `?token=`
- [ ] Обновить обработчик событий (switch по `type`)
- [ ] Заменить HTTP POST на `ws.send()` для отправки сообщений
- [ ] Реализовать авто-переподключение с exponential backoff
- [ ] Отвечать `pong` на `ping` для поддержания соединения
- [ ] Обработать состояния: connecting, open, closing, closed
- [ ] Показывать индикатор состояния соединения пользователю

---

## Тестирование

### Локально
```bash
# Запустить тестовый клиент
python scripts/test_websocket.py \
  --token YOUR_JWT_TOKEN \
  --agent-id AGENT_UUID \
  --url ws://localhost:8000/api/v1
```

### В браузере (DevTools Console)
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/agents/AGENT_ID/ws?token=TOKEN');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({ type: 'get_status' }));
```

---

## Примечания

1. **SSE пока остаётся** для обратной совместимости, но будет удалён после миграции фронтенда
2. **Один WebSocket на агента** — достаточно одного соединения для всех диалогов агента
3. **Ping каждые 20 секунд** — сервер отправляет ping, клиент должен отвечать pong
4. **Коды закрытия:**
   - `1008` — неавторизован (неверный токен)
   - `1000` — нормальное закрытие
