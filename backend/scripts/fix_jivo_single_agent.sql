-- ============================================================================
-- Скрипт обновления конфигурации Jivo для системы с одним агентом
-- ============================================================================
-- Назначение: Обновить единственный активный канал Jivo на новые учётные данные
-- Дата создания: 2026-08-05
-- ============================================================================

\echo '>>> Начинаем обновление канала Jivo...'
\echo ''

-- Проверяем наличие единственного активного канала Jivo
\echo '>>> Шаг 1: Поиск активного канала Jivo'
SELECT 
    id,
    agent_id,
    name,
    type,
    jivo_provider_id AS current_provider_id,
    is_deleted
FROM channels 
WHERE type = 'jivo' 
  AND is_deleted = false;

\echo ''
\echo '>>> Шаг 2: Обновление учётных данных Jivo'

-- Обновляем единственный канал Jivo
WITH update_result AS (
    UPDATE channels
    SET 
        jivo_provider_token = 'CAJLGey0-s4-2Af_T1HpEnmCVZgkxh7aBZHfrpCwiB8',
        jivo_provider_id = 'MKBRrqKKf6xM0Jo',
        jivo_reply_base_url = 'https://bot.jivosite.com/webhooks/MKBRrqKKf6xM0Jo',
        updated_at = CURRENT_TIMESTAMP
    WHERE type = 'jivo' 
      AND is_deleted = false
    RETURNING 
        id,
        agent_id,
        name,
        type,
        jivo_provider_id,
        jivo_reply_base_url,
        updated_at
)
SELECT 
    COUNT(*) as updated_count,
    'Обновлено записей: ' || COUNT(*) as status_message
FROM update_result;

\echo ''
\echo '>>> Шаг 3: Проверка результата обновления'

-- Показываем обновлённый канал с полной информацией
SELECT 
    id AS channel_id,
    agent_id,
    name AS channel_name,
    type,
    jivo_provider_id,
    jivo_reply_base_url AS webhook_url,
    is_deleted,
    updated_at
FROM channels 
WHERE type = 'jivo' 
  AND is_deleted = false;

\echo ''
\echo '>>> ВАЖНО: Webhook URL для настройки в Jivo:'
SELECT jivo_reply_base_url AS webhook_url
FROM channels 
WHERE type = 'jivo' 
  AND is_deleted = false;

\echo ''
\echo '>>> Обновление завершено успешно!'
\echo '>>> Скопируйте webhook URL выше и настройте его в панели Jivo.'
\echo ''

-- ============================================================================
-- ИНСТРУКЦИЯ ПО ВЫПОЛНЕНИЮ
-- ============================================================================
--
-- Вариант 1: Выполнение через Docker Compose (рекомендуется)
-- ------------------------------------------------------------
-- docker compose exec db psql -U postgres -d agents_dev -f /docker-entrypoint-initdb.d/fix_jivo_single_agent.sql
--
-- Примечание: Убедитесь, что скрипт смонтирован в контейнер или скопируйте его:
-- docker cp backend/scripts/fix_jivo_single_agent.sql <container_id>:/tmp/
-- docker compose exec db psql -U postgres -d agents_dev -f /tmp/fix_jivo_single_agent.sql
--
--
-- Вариант 2: Выполнение через docker exec
-- ----------------------------------------
-- docker exec -i <postgres_container_name> psql -U postgres -d agents_dev < backend/scripts/fix_jivo_single_agent.sql
--
--
-- Вариант 3: Копирование и выполнение внутри контейнера
-- -----------------------------------------------------
-- # Скопировать скрипт в контейнер
-- docker cp backend/scripts/fix_jivo_single_agent.sql <container_id>:/tmp/fix_jivo.sql
--
-- # Выполнить скрипт
-- docker exec -it <container_id> psql -U postgres -d agents_dev -f /tmp/fix_jivo.sql
--
--
-- Вариант 4: Выполнение из локальной psql (если есть доступ к БД)
-- ----------------------------------------------------------------
-- psql -h localhost -U postgres -d agents_dev -f backend/scripts/fix_jivo_single_agent.sql
--
--
-- ПРОВЕРКА РЕЗУЛЬТАТА:
-- --------------------
-- После выполнения скрипт должен показать:
-- 1. Информацию о найденном канале (до обновления)
-- 2. Количество обновлённых записей (должно быть ровно 1)
-- 3. Обновлённые данные канала с новым webhook URL
-- 4. Webhook URL для копирования в настройки Jivo
--
-- ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:
-- updated_count = 1
-- webhook_url = https://bot.jivosite.com/webhooks/MKBRrqKKf6xM0Jo
--
-- ============================================================================
