# SQNS Hourly Sync: ручной чек-лист

## Что уже проверено на этапе реализации

- [x] Python-синтаксис backend: `python3 -m compileall app`
- [x] Python-синтаксис миграции: `python3 -m py_compile alembic/versions/0045_sqns_hourly_sync_storage.py`
- [x] Синтаксис docker-compose: `docker compose -f myapp/infra/docker-compose.yml config`
- [x] IDE lint-проверка измененных файлов (ошибок не найдено)

## Что нужно проверить в окружении с поднятой БД/SQNS

### 1) Применение миграции

- [ ] Выполнить: `alembic -c /app/alembic.ini upgrade head`
- [ ] Проверить наличие таблиц:
  - `sqns_commodities`
  - `sqns_employees`
  - `sqns_clients`
  - `sqns_visits`
  - `sqns_payments`
  - `sqns_sync_cursor`
  - `sqns_sync_runs`
- [ ] Проверить наличие колонки `agents.sqns_last_activity_at`

### 2) Запуск worker

- [ ] Поднять сервис: `docker compose -f myapp/infra/docker-compose.yml up -d sqns-sync-worker`
- [ ] Проверить логи старта: `docker compose -f myapp/infra/docker-compose.yml logs sqns-sync-worker --tail 200`
- [ ] Убедиться, что цикл запускается с интервалом `SQNS_SYNC_INTERVAL_SECONDS`

### 3) Полный проход синхронизации

- [ ] У агента `sqns_enabled=true` и валидный credential
- [ ] Дождаться одного цикла worker и проверить:
  - `agents.sqns_status = 'ok'`
  - `agents.sqns_last_sync_at` заполнено
  - `agents.sqns_last_activity_at` заполнено
- [ ] Проверить заполнение таблиц `sqns_services`, `sqns_commodities`, `sqns_employees`, `sqns_visits`, `sqns_payments`
- [ ] Проверить заполнение таблицы `sqns_clients` (PII поля — в зашифрованном `pii_data`)
- [ ] Проверить запись в `sqns_sync_runs` со `status='success'`
- [ ] Проверить курсоры в `sqns_sync_cursor` для сущностей: `employees/clients/services/commodities/visits/payments`

### 4) Ручной sync endpoint

- [ ] Вызвать `POST /api/v1/agents/{agent_id}/sqns/sync`
- [ ] Проверить, что ответ содержит новые счетчики:
  - `employees_synced`
  - `clients_synced`
  - `commodities_synced`
  - `visits_synced`
  - `payments_synced`
- [ ] Проверить, что при success обновляются:
  - `sqns_last_sync_at`
  - `sqns_last_activity_at`

### 5) Проверка lock

- [ ] Запустить параллельно 2 ручных sync-запроса для одного агента
- [ ] Ожидаемое поведение:
  - один запрос выполняется
  - второй получает `409` с текстом про уже идущую синхронизацию

### 6) Проверка окна платежей

- [ ] По умолчанию используется окно 30 дней (`SQNS_SYNC_PAYMENTS_WINDOW_DAYS=30`)
- [ ] При необходимости изменить `SQNS_SYNC_PAYMENTS_WINDOW_DAYS` (<=90)
- [ ] Проверить, что в логах/курсоре используется диапазон не больше 90 дней
- [ ] Убедиться, что таблица `sqns_payments` обновляется upsert-логикой без дублей по `external_id`

### 7) Проверка окна визитов

- [ ] По умолчанию используется окно 30 дней (`SQNS_SYNC_VISITS_WINDOW_DAYS=30`)
- [ ] При необходимости изменить `SQNS_SYNC_VISITS_WINDOW_DAYS` (<=365)
- [ ] Проверить, что `sqns_visits` обновляется в выбранном диапазоне
