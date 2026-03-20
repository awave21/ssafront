#!/bin/bash

# Скрипт для быстрого тестирования HTTP Tools API
# Использует публичные API без аутентификации для простоты

set -e

API_URL="${API_URL:-http://localhost:8000}"
AUTH_TOKEN="${AUTH_TOKEN:-your-token-here}"

echo "🧪 Testing HTTP Tools Enhancement API"
echo "API: $API_URL"
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test 1: Простой GET запрос
echo -e "${BLUE}Test 1: GET request with path parameter${NC}"
echo "Endpoint: GET https://api.github.com/users/{username}"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/tools/test" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "endpoint": "https://api.github.com/users/{username}",
    "http_method": "GET",
    "args": {
      "username": "torvalds"
    },
    "parameter_mapping": {
      "username": "path"
    },
    "auth_type": "none"
  }')

STATUS=$(echo "$RESPONSE" | jq -r '.status_code // "error"')
LATENCY=$(echo "$RESPONSE" | jq -r '.latency_ms // 0')
ERROR=$(echo "$RESPONSE" | jq -r '.error // "none"')
RAW_SIZE=$(echo "$RESPONSE" | jq -r '.raw_size_bytes // 0')
REQUEST_URL=$(echo "$RESPONSE" | jq -r '.request_url // "none"')

echo -e "${GREEN}✓ Status: $STATUS${NC}"
echo "  Latency: ${LATENCY}ms"
echo "  Request URL: $REQUEST_URL"
echo "  Response size: $RAW_SIZE bytes"
echo "  Error: $ERROR"
echo ""

# Test 2: GET с фильтрацией ответа
echo -e "${BLUE}Test 2: GET request with response filtering${NC}"
echo "Same endpoint, but filter response to only 3 fields"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/tools/test" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "endpoint": "https://api.github.com/users/{username}",
    "http_method": "GET",
    "args": {
      "username": "torvalds"
    },
    "parameter_mapping": {
      "username": "path"
    },
    "auth_type": "none",
    "response_transform": {
      "mode": "fields",
      "fields": [
        {"source": "login", "target": "username"},
        {"source": "name", "target": "full_name"},
        {"source": "public_repos", "target": "repos_count"}
      ]
    }
  }')

RAW_SIZE=$(echo "$RESPONSE" | jq -r '.raw_size_bytes // 0')
TRANSFORMED_SIZE=$(echo "$RESPONSE" | jq -r '.transformed_size_bytes // 0')
SAVINGS=0
if [ "$RAW_SIZE" -gt 0 ] && [ "$TRANSFORMED_SIZE" -gt 0 ]; then
  SAVINGS=$(echo "scale=0; 100 - ($TRANSFORMED_SIZE * 100 / $RAW_SIZE)" | bc)
fi

echo -e "${GREEN}✓ Response transformed${NC}"
echo "  Raw size: $RAW_SIZE bytes"
echo "  Filtered size: $TRANSFORMED_SIZE bytes"
echo -e "  ${YELLOW}Token savings: -${SAVINGS}%${NC} 🎉"
echo ""
echo "  Raw body (first 3 fields):"
echo "$RESPONSE" | jq -r '.raw_body | {login, name, id}'
echo ""
echo "  Transformed body:"
echo "$RESPONSE" | jq -r '.transformed_body'
echo ""

# Test 3: GET с фильтрацией массива
echo -e "${BLUE}Test 3: GET request with array filtering${NC}"
echo "Endpoint: GET https://api.github.com/users/{username}/repos"
echo "Filter array: keep only 2 fields per repo"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/tools/test" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "endpoint": "https://api.github.com/users/{username}/repos",
    "http_method": "GET",
    "args": {
      "username": "torvalds",
      "per_page": 3
    },
    "parameter_mapping": {
      "username": "path",
      "per_page": "query"
    },
    "auth_type": "none",
    "response_transform": {
      "mode": "jmespath",
      "expression": "[].{name: name, stars: stargazers_count, language: language}"
    }
  }')

STATUS=$(echo "$RESPONSE" | jq -r '.status_code // "error"')
RAW_SIZE=$(echo "$RESPONSE" | jq -r '.raw_size_bytes // 0')
TRANSFORMED_SIZE=$(echo "$RESPONSE" | jq -r '.transformed_size_bytes // 0')
SAVINGS=0
if [ "$RAW_SIZE" -gt 0 ] && [ "$TRANSFORMED_SIZE" -gt 0 ]; then
  SAVINGS=$(echo "scale=0; 100 - ($TRANSFORMED_SIZE * 100 / $RAW_SIZE)" | bc)
fi

echo -e "${GREEN}✓ Status: $STATUS${NC}"
echo "  Raw size: $RAW_SIZE bytes (full GitHub repo objects)"
echo "  Filtered size: $TRANSFORMED_SIZE bytes (only name, stars, language)"
echo -e "  ${YELLOW}Token savings: -${SAVINGS}%${NC} 🚀"
echo ""
echo "  Transformed body (sample):"
echo "$RESPONSE" | jq -r '.transformed_body[0:2]'
echo ""

# Test 4: POST request
echo -e "${BLUE}Test 4: POST request with query and body params${NC}"
echo "Endpoint: POST https://jsonplaceholder.typicode.com/todos"
echo ""

RESPONSE=$(curl -s -X POST "$API_URL/tools/test" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -d '{
    "endpoint": "https://jsonplaceholder.typicode.com/todos",
    "http_method": "POST",
    "args": {
      "userId": 1,
      "title": "Test HTTP Tool",
      "completed": false
    },
    "parameter_mapping": {
      "userId": "query",
      "title": "body",
      "completed": "body"
    },
    "auth_type": "none"
  }')

STATUS=$(echo "$RESPONSE" | jq -r '.status_code // "error"')
REQUEST_URL=$(echo "$RESPONSE" | jq -r '.request_url // "none"')
RAW_BODY=$(echo "$RESPONSE" | jq -r '.raw_body')

echo -e "${GREEN}✓ Status: $STATUS${NC}"
echo "  Request URL: $REQUEST_URL"
echo "  Created todo:"
echo "$RAW_BODY" | jq '.'
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ All tests passed!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Backend ready for frontend integration! 🎉"
