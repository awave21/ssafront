-- Диагностика последнего активного Telegram-диалога (по времени run).
-- Запуск на сервере, из каталога infra:
--   docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f - < ../backend/scripts/diag_last_telegram_dialog.sql
-- или скопировать блоки в psql.

WITH last_sessions AS (
    SELECT
        session_id,
        agent_id,
        MAX(created_at) AS last_run_at,
        COUNT(*) FILTER (WHERE status = 'failed') AS failed_runs,
        COUNT(*) FILTER (WHERE status = 'succeeded') AS ok_runs
    FROM runs
    WHERE session_id LIKE 'telegram:%'
    GROUP BY session_id, agent_id
    ORDER BY last_run_at DESC
    LIMIT 5
)
SELECT
    ls.session_id,
    ls.agent_id,
    ls.last_run_at,
    ls.failed_runs,
    ls.ok_runs,
    ds.status AS dialog_state_status,
    ds.last_manager_message_at,
    aus.is_disabled AS agent_user_disabled,
    aus.disabled_at,
    a.is_disabled AS agent_globally_disabled
FROM last_sessions ls
LEFT JOIN dialog_states ds
    ON ds.session_id = ls.session_id AND ds.agent_id = ls.agent_id
LEFT JOIN agent_user_states aus
    ON aus.agent_id = ls.agent_id
    AND aus.platform = 'telegram'
    AND aus.platform_user_id = SUBSTRING(ls.session_id FROM LENGTH('telegram:') + 1)
LEFT JOIN agents a ON a.id = ls.agent_id
ORDER BY ls.last_run_at DESC;

-- Последний run по самому свежему telegram-сессии (детали ответа):
WITH top AS (
    SELECT session_id, agent_id
    FROM runs
    WHERE session_id LIKE 'telegram:%'
    GROUP BY session_id, agent_id
    ORDER BY MAX(created_at) DESC
    LIMIT 1
)
SELECT r.id, r.created_at, r.status, r.error_message,
       LEFT(r.input_message, 200) AS input_preview,
       LEFT(COALESCE(r.output_message, ''), 300) AS output_preview,
       r.tools_called IS NOT NULL AND r.tools_called::text != '[]' AS had_tools
FROM runs r
JOIN top t ON r.session_id = t.session_id AND r.agent_id = t.agent_id
ORDER BY r.created_at DESC
LIMIT 3;
