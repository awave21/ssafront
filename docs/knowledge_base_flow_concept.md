# Концептуальная схема: как база знаний попадает в систему

```mermaid
flowchart TD
    A[Источник знаний\nTXT/PDF/DOCX/CSV или ручной текст] --> B[API\nPOST /agents/:id/knowledge-files/upload\nили POST /agents/:id/knowledge-files]
    B --> C[(knowledge_files)\nfile node: content, title, meta_tags,\nvector_status=not_indexed]
    C --> D[Запуск индексации\nPOST /agents/:id/knowledge-files/:item_id/index]
    D --> E[(knowledge_index_jobs)\nqueued -> indexing -> indexed/failed]
    E --> F[Чанкинг текста\nchunk_text_by_chars\n(+ настройки папки chunk_size/overlap)]
    F --> G[Генерация embedding для каждого чанка\ncreate_embedding(OpenAI)]
    G --> H[(knowledge_file_chunks)\nchunk_text + embedding(vector)]
    H --> I[Файл помечается indexed\nknowledge_files.vector_status=indexed]

    I --> J[Runtime: build_knowledge_search_tool]
    J --> K[LLM tool call: search_knowledge_files(query)]
    K --> L[Векторный поиск по knowledge_file_chunks\ncosine distance / pgvector]
    L --> M[Топ релевантных фрагментов\nвозвращаются в агент]
    M --> N[LLM формирует финальный ответ пользователю]
```

## Коротко по этапам

- **1) Загрузка контента**: файл загружается через `upload` (или создается как текстовый узел), запись попадает в `knowledge_files`.
- **2) Индексация отдельно**: запуск индексации делается отдельным API-вызовом, создается `knowledge_index_jobs`.
- **3) Чанкинг и эмбеддинги**: текст режется на чанки, для каждого чанка считается embedding и пишется в `knowledge_file_chunks`.
- **4) Статус файла**: после успешной обработки `vector_status` становится `indexed` (или `failed` при ошибке).
- **5) Использование в диалоге**: во время `execute_agent_run` агент получает tool `search_knowledge_files`; LLM сам решает, вызывать его или нет.
- **6) Ответ пользователю**: LLM использует найденные фрагменты как контекст и генерирует финальный ответ.

## Важные уточнения

- Индексация **асинхронная** (background task + polling job status).
- Без OpenAI API key индексация/поиск по knowledge не работают.
- При обновлении контента файла статус сбрасывается в `not_indexed`, нужен повторный `index`.
- Настройки чанкинга могут наследоваться от папки (`chunk_size_chars`, `chunk_overlap_chars`), и это может триггерить массовый reindex потомков.
