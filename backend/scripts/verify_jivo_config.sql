-- ============================================================================
-- Проверка и обновление конфигурации Jivo
-- На основе данных от технической поддержки Jivo (05.08.2026)
-- ============================================================================

\echo '>>> Шаг 1: Текущее состояние Jivo каналов'
\echo ''

SELECT 
    id AS channel_id,
    name AS channel_name,
    type,
    jivo_provider_id,
    jivo_provider_token,
    jivo_reply_base_url,
    is_deleted,
    created_at,
    updated_at
FROM channels
WHERE type = 'jivo'
ORDER BY created_at DESC;

\echo ''
\echo '>>> Шаг 2: Проверка связей канал-агент'
\echo ''

SELECT 
    c.id AS channel_id,
    c.name AS channel_name,
    a.id AS agent_id,
    a.name AS agent_name,
    a.is_deleted AS agent_deleted
FROM channels c
JOIN agents_channels ac ON ac.channel_id = c.id
JOIN agents a ON a.id = ac.agent_id
WHERE c.type = 'jivo' AND c.is_deleted = false;

\echo ''
\echo '>>> Шаг 3: Обновление конфигурации (если нужно)'
\echo ''

-- Обновляем все активные Jivo каналы правильными данными
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
    name,
    jivo_provider_id,
    jivo_reply_base_url,
    'Обновлено' AS status;

\echo ''
\echo '>>> Шаг 4: Финальная проверка'
\echo ''

SELECT 
    id AS channel_id,
    name,
    'https://api.chatmedbot.ru/api/v1/webhooks/jivo/' || jivo_provider_token AS webhook_endpoint,
    'https://bot.jivosite.com/webhooks/' || jivo_provider_id || '/' || jivo_provider_token AS full_reply_url,
    is_deleted
FROM channels
WHERE type = 'jivo' AND is_deleted = false;

\echo ''
\echo '============================================================================'
\echo 'КОНФИГУРАЦИЯ ПО ДАННЫМ ОТ JIVO SUPPORT:'
\echo '============================================================================'
\echo 'Provider ID: MKBRrqKKf6xM0Jo'
\echo 'Webhook Endpoint (входящие от Jivo):'
\echo '  https://api.chatmedbot.ru/api/v1/webhooks/jivo/CAJLGey0-s4-2Af_T1HpEnmCVZgkxh7aBZHfrpCwiB8'
\echo ''
\echo 'Reply URL (исходящие в Jivo):'
\echo '  https://bot.jivosite.com/webhooks/MKBRrqKKf6xM0Jo/CAJLGey0-s4-2Af_T1HpEnmCVZgkxh7aBZHfrpCwiB8'
\echo ''
\echo '============================================================================'
\echo ''
