-- Список агентов и превью system_prompt (полный текст — по id отдельным запросом ниже).
-- Запуск с хоста, из каталога infra (подставятся переменные из .env compose):
--   docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f - < ../backend/scripts/dump_agent_system_prompt.sql
-- Или одной строкой без файла:
--   docker compose exec -T db psql -U postgres -d agents -c "SELECT id, name, status, version, length(system_prompt) AS prompt_chars, left(system_prompt, 150) AS preview FROM agents WHERE deleted_at IS NULL ORDER BY updated_at DESC;"

SELECT
    id,
    name,
    status,
    version,
    sqns_enabled,
    length(system_prompt) AS prompt_chars,
    left(system_prompt, 200) AS prompt_preview
FROM agents
WHERE deleted_at IS NULL
ORDER BY updated_at DESC NULLS LAST;

-- Полный system_prompt для агента Face Clinic (ЛК: …/agents/176548eb-cce1-4ca8-8775-1f24d45a1b6d/prompt):
SELECT system_prompt FROM agents WHERE id = '176548eb-cce1-4ca8-8775-1f24d45a1b6d'::uuid;

-- Активная версия из истории (если используете версионирование):
-- SELECT v.id, v.version, v.is_active, length(v.system_prompt) AS len, left(v.system_prompt, 200)
-- FROM system_prompt_versions v
-- WHERE v.agent_id = '00000000-0000-0000-0000-000000000000'::uuid
-- ORDER BY v.is_active DESC, v.created_at DESC
-- LIMIT 5;
