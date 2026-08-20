-- Запрос для поиска всех Jivo каналов с дополнительной информацией об агентах
SELECT 
    c.id AS channel_id,
    ac.agent_id,
    c.jivo_provider_token,
    c.jivo_provider_id,
    c.jivo_reply_base_url,
    c.created_at,
    c.updated_at,
    c.is_deleted
FROM 
    channels c
LEFT JOIN 
    agent_channels ac ON c.id = ac.channel_id
WHERE 
    c.type = 'jivo'
    AND c.is_deleted = false
ORDER BY 
    c.created_at DESC;
