#!/bin/bash
# Простая проверка канала Jivo через psql

TOKEN="CAJLGey0-s4-2Af_T1HpEnmCVZgkxh7aBZHfrpCwiB8"

echo "=== Проверка канала Jivo в БД ==="
echo ""

# Пытаемся подключиться к БД (предполагаем localhost:5432)
PGPASSWORD=postgres psql -h localhost -U postgres -d agents_dev -c "
SELECT 
    id, 
    name, 
    type, 
    jivo_provider_token,
    jivo_provider_id,
    jivo_reply_base_url,
    is_deleted
FROM channels
WHERE type = 'jivo' AND is_deleted = false;
" 2>&1

echo ""
echo "=== Поиск канала с токеном ${TOKEN:0:20}... ==="
PGPASSWORD=postgres psql -h localhost -U postgres -d agents_dev -c "
SELECT COUNT(*) as found
FROM channels
WHERE type = 'jivo' 
  AND is_deleted = false 
  AND jivo_provider_token = '$TOKEN';
" 2>&1
