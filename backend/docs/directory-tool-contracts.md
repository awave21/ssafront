# Directory Tool Contracts (Backend)

## 1) Template -> Function Name Mapping

For template-based directories, `tool_name` is fixed by backend:

- `qa` -> `get_question_answer`
- `service_catalog` -> `get_service_info`
- `product_catalog` -> `get_product_info`
- `company_info` -> `get_company_info`
- `theme_catalog` -> `get_topic_info`
- `medical_course_catalog` -> `get_medical_course_info`

For `custom` template:

- `tool_name` uses payload value when provided
- fallback: normalized value from directory name (`snake_case`)

## 2) Directory Create/Update Rules

### Create (`POST /agents/{agent_id}/directories`)

- For `qa`:
  - columns are fixed to `question/answer`
  - search type is forced to `semantic`
  - tool name is forced to `get_question_answer`
- For other mapped templates:
  - tool name is forced by mapping
  - default `tool_description` is prefilled by backend if empty
- For `custom`:
  - tool name may be user-defined

### Update (`PUT /agents/{agent_id}/directories/{directory_id}`)

- For `qa`:
  - changing `columns` is forbidden
  - changing `search_type` away from `semantic` is forbidden
  - `tool_name` stays fixed (`get_question_answer`)
- For mapped templates:
  - `tool_name` remains fixed by backend

## 3) Runtime Registration

- Auto-registration of directory tools includes only `template=qa`.
- Non-qa directories (tables) are not auto-tools in runtime.

## 4) Tool Input Contract

Directory tool input schema:

```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "description": "Поисковый запрос для поиска по справочнику" }
  },
  "required": []
}
```

## 5) Tool Output Contract

### Common fields

- `status`: `ok | no_match | error`
- `mode`: `direct_message | function_result`
- `message`: summary text
- `items`: result list

### `mode=direct_message`

- Must be treated as user-facing final text.
- For `qa`, `message` is exact value of top matched `answer`.
- Additional field: `exact_user_message` (same as `message`).

Example:

```json
{
  "status": "ok",
  "mode": "direct_message",
  "message": "Доставка занимает 1-2 дня.",
  "exact_user_message": "Доставка занимает 1-2 дня.",
  "items": [{ "id": "uuid", "data": { "question": "...", "answer": "..." } }]
}
```

### `mode=function_result`

- LLM should generate final response from returned data.
- Structured payload includes `total` and `items`.

Example:

```json
{
  "status": "ok",
  "mode": "function_result",
  "message": "Найдено 2 результатов",
  "total": 2,
  "items": [
    { "id": "uuid-1", "data": { "name": "A", "price": 1000 }, "relevance": 0.91 },
    { "id": "uuid-2", "data": { "name": "B", "price": 1200 }, "relevance": 0.86 }
  ]
}
```

## 6) Agent Behavior Contract

- If tool output mode is `direct_message`, agent should pass `message` to user without paraphrasing.
- If mode is `function_result`, agent may synthesize user response from `items` and `message`.
