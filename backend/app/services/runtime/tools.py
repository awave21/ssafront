from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from pydantic_ai.tools import Tool as PydanticTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.binding import AgentToolBinding
from app.db.models.direct_question import DirectQuestion
from app.db.models.knowledge_file import KnowledgeFile
from app.db.models.tool import Tool
from app.db.session import async_session_factory
from app.schemas.auth import AuthContext
from app.services.credentials import decrypt_config
from app.services.direct_questions.safety import sanitize_direct_question_content, split_direct_question_content
from app.services.direct_questions.retrieval import search_direct_question_candidates
from app.services.knowledge_files import search_indexed_knowledge_files
from app.services.function_rules_runtime import run_rules_for_phase
from app.services.tool_executor import ToolExecutionError, execute_tool_call, transform_response
from app.services.runtime.utils import _safe_identifier

logger = structlog.get_logger("app.services.runtime")


def _tool_result_to_log_dict(value: Any) -> dict[str, Any] | None:
    """Coerce tool return value to a JSONB-friendly dict for tool_call_logs / analytics."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    if isinstance(value, (str, int, float, bool)):
        return {"value": value}
    return {"value": str(value)}


DEFAULT_KNOWLEDGE_SEARCH_TOOL_DESCRIPTION = (
    "Data tool: search indexed uploaded files (RAG). "
    "Returns chunk_id, file_id, chunk_index, title, excerpt — cite when answering. "
    "Prefer this for long documents and file-based guides. "
    "The agent also has other data tools (named catalog searches and `search_direct_questions` / `get_direct_answer`); "
    "pick whichever tool's description fits the question."
)


def _normalize_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Конвертировать кастомный _variables в стандартный properties.
    
    Для обратной совместимости со старыми инструментами, созданными
    на фронтенде с использованием нестандартного поля _variables.
    
    Args:
        input_schema: JSON Schema с возможным полем _variables
        
    Returns:
        Нормализованная схема с правильным properties
    """
    # Если есть _variables и properties пустой/отсутствует
    if '_variables' in input_schema:
        properties = input_schema.get('properties', {})
        
        # Конвертируем _variables в properties
        for var in input_schema.get('_variables', []):
            if not isinstance(var, dict):
                continue
                
            var_name = var.get('name')
            if not var_name:
                continue
            
            # Не перезаписываем существующий property
            if var_name in properties:
                continue
            
            # Создаём property из variable
            properties[var_name] = {
                'type': var.get('type', 'string'),
                'description': var.get('description', f'Параметр {var_name}'),
                'x-fromAI': True,  # Переменные всегда должны заполняться AI
            }
            
            # Добавляем default если есть
            if 'value' in var:
                properties[var_name]['default'] = var['value']
        
        # Создаём новую схему с обновлёнными properties
        normalized = {**input_schema, 'properties': properties}
        
        logger.info(
            "input_schema_normalized",
            variables_converted=len(input_schema.get('_variables', [])),
            properties_added=len(properties) - len(input_schema.get('properties', {})),
        )
        
        return normalized
    
    return input_schema


def _build_llm_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Построить JSON Schema только из x-fromAI параметров для LLM.

    Если ни одно свойство не имеет x-fromAI — возвращает оригинальную схему
    (обратная совместимость для инструментов без этого флага).
    """
    properties = input_schema.get("properties", {})
    has_from_ai = any(
        isinstance(p, dict) and p.get("x-fromAI") is True
        for p in properties.values()
    )
    if not has_from_ai:
        return input_schema

    ai_properties: dict[str, Any] = {}
    ai_required: list[str] = []

    for key, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        if prop.get("x-fromAI") is True:
            # Убираем x-fromAI — LLM его не понимает
            clean_prop = {k: v for k, v in prop.items() if k != "x-fromAI"}
            ai_properties[key] = clean_prop
            # Если нет default — параметр обязательный для LLM
            if "default" not in prop:
                ai_required.append(key)

    return {
        "type": "object",
        "properties": ai_properties,
        "required": ai_required,
        "additionalProperties": False,
    }


def _merge_tool_args(
    input_schema: dict[str, Any], llm_args: dict[str, Any],
) -> dict[str, Any]:
    """
    Смержить AI-аргументы от LLM со статическими default из схемы.

    Если ни одно свойство не имеет x-fromAI — возвращает оригинальные аргументы
    (обратная совместимость).
    """
    properties = input_schema.get("properties", {})
    has_from_ai = any(
        isinstance(p, dict) and p.get("x-fromAI") is True
        for p in properties.values()
    )
    if not has_from_ai:
        return llm_args

    merged: dict[str, Any] = {}
    for key, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        if prop.get("x-fromAI") is True:
            # AI-параметр: берём значение от LLM (или fallback на default)
            if key in llm_args:
                merged[key] = llm_args[key]
            elif "default" in prop:
                merged[key] = prop["default"]
        else:
            # Статический параметр: берём default из схемы
            if "default" in prop:
                merged[key] = prop["default"]
    return merged


def _build_tool_wrapper(
    tool: Tool,
    binding: AgentToolBinding,
    *,
    agent_id: UUID | None,
    session_id: str | None,
    trace_id: str,
    user: AuthContext,
    tool_events: list[dict[str, Any]] | None = None,
) -> PydanticTool:
    """
    Создать pydantic-ai Tool из нашей DB модели БЕЗ exec().

    Использует Tool.from_schema() для создания инструмента с правильной JSON Schema.
    """
    async def _tool_impl(**kwargs: Any) -> Any:
        started_at = datetime.now(timezone.utc)
        transformed_result: Any = None
        final_args: dict[str, Any] = {}
        if binding.permission_scope == "write" and "tools:write" not in user.scopes:
            raise ToolExecutionError("Missing tools:write scope")
        if tool.execution_type not in {"http_webhook", "internal"}:
            raise ToolExecutionError("Unsupported tool execution type")
        if tool.execution_type == "http_webhook" and not tool.endpoint:
            raise ToolExecutionError("Unsupported tool execution type")
        secret_payload = None
        if binding.credential and binding.credential.is_active:
            try:
                secret_payload = decrypt_config(binding.credential.config)
            except ValueError as exc:
                raise ToolExecutionError("Invalid credential config") from exc
        
        # Смержить AI-аргументы от LLM со статическими default
        # Используем нормализованную схему
        try:
            final_args = _merge_tool_args(normalized_schema, kwargs)

            if tool.execution_type == "internal":
                # Internal tools do not perform HTTP calls.
                transformed_result = {
                    "mode": "internal",
                    "tool_name": tool.name,
                    "args": final_args,
                    "status": "ok",
                }
            else:
                # Вызвать tool
                raw_result = await execute_tool_call(
                    tool.endpoint,
                    tool.input_schema,
                    final_args,
                    trace_id=trace_id,
                    auth_type=tool.auth_type,
                    http_method=tool.http_method or "POST",
                    parameter_mapping=tool.parameter_mapping,
                    custom_headers=tool.custom_headers,
                    secrets_ref=binding.secrets_ref,
                    secret_payload=secret_payload,
                    allowed_domains=binding.allowed_domains,
                    timeout_ms=binding.timeout_ms,
                    user=user,
                )
                transformed_result = raw_result
                # Применить response_transform если настроен
                if tool.response_transform:
                    transformed_result = transform_response(raw_result, tool.response_transform)

            # Post-actions/reactions are attached to a specific tool and run
            # only after this exact tool call succeeds.
            if agent_id and session_id:
                try:
                    async with async_session_factory() as db:
                        _, post_tool_context = await run_rules_for_phase(
                            db,
                            tenant_id=tool.tenant_id,
                            agent_id=agent_id,
                            session_id=session_id,
                            trace_id=trace_id,
                            phase="post_tool",
                            message=f"tool:{tool.name}",
                            user=user,
                            run_id=None,
                            context={
                                "tool_name": tool.name,
                                "tool_args": final_args,
                                "tool_call_args": final_args,
                                "tool_result": transformed_result,
                                "last_tool_result": transformed_result,
                                "skip_rule_tool_execution": True,
                            },
                            rules_enabled=True,
                            semantic_allowed=False,
                            tool_id_filter=tool.id,
                        )
                        await db.commit()
                        # Make post-tool AI instruction visible to the model in the same turn.
                        # This is a pragmatic replacement for removed pre/post-run prompt merging.
                        extra_instructions = post_tool_context.get("augment_prompt", [])
                        if isinstance(extra_instructions, list):
                            rendered = [str(item).strip() for item in extra_instructions if str(item).strip()]
                        else:
                            rendered = []
                        if rendered:
                            if isinstance(transformed_result, dict):
                                transformed_result = {
                                    **transformed_result,
                                    "__post_tool_ai_instruction": "\n".join(rendered),
                                }
                            else:
                                transformed_result = {
                                    "result": transformed_result,
                                    "__post_tool_ai_instruction": "\n".join(rendered),
                                }
                        queued_messages = post_tool_context.get("messages_to_send", [])
                        if isinstance(queued_messages, list):
                            rendered_messages = [str(item).strip() for item in queued_messages if str(item).strip()]
                        else:
                            rendered_messages = []
                        if rendered_messages:
                            if isinstance(transformed_result, dict):
                                transformed_result = {
                                    **transformed_result,
                                    "__post_tool_reaction_messages": rendered_messages,
                                }
                            else:
                                transformed_result = {
                                    "result": transformed_result,
                                    "__post_tool_reaction_messages": rendered_messages,
                                }
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "tool_post_actions_failed",
                        tool_name=tool.name,
                        agent_id=str(agent_id),
                        session_id=session_id,
                        error=str(exc),
                    )

            if tool_events is not None:
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)
                tool_events.append(
                    {
                        "tool_name": tool.name,
                        "tool_id": str(tool.id),
                        "status": "success",
                        "invoked_at": started_at,
                        "duration_ms": max(duration_ms, 0),
                        "request_payload": final_args,
                        "response_payload": _tool_result_to_log_dict(transformed_result),
                        "error_payload": None,
                    }
                )
            return transformed_result
        except Exception as exc:
            if tool_events is not None:
                finished_at = datetime.now(timezone.utc)
                duration_ms = int((finished_at - started_at).total_seconds() * 1000)
                error_payload: dict[str, Any] = {
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
                tool_events.append(
                    {
                        "tool_name": tool.name,
                        "tool_id": str(tool.id),
                        "status": "error",
                        "invoked_at": started_at,
                        "duration_ms": max(duration_ms, 0),
                        "request_payload": final_args if isinstance(final_args, dict) else {},
                        "response_payload": None,
                        "error_payload": error_payload,
                    }
                )
            raise

    _tool_impl.__name__ = _safe_identifier(tool.name)
    _tool_impl.__doc__ = tool.description or tool.name

    # Нормализуем input_schema (конвертируем _variables → properties)
    normalized_schema = _normalize_input_schema(tool.input_schema)
    
    # LLM видит только x-fromAI параметры (если они есть)
    llm_schema = _build_llm_schema(normalized_schema)

    return PydanticTool.from_schema(
        function=_tool_impl,
        name=tool.name,
        description=tool.description,
        json_schema=llm_schema,
        takes_ctx=False,
    )


def build_direct_answer_tool(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
) -> PydanticTool:
    """Runtime data tool: одна карточка прямого вопроса по UUID (рядом с остальными data-тулами агента)."""

    async def _get_direct_answer(direct_question_id: str) -> dict[str, Any]:
        question_uuid = None
        try:
            question_uuid = UUID(str(direct_question_id))
        except (ValueError, TypeError):
            return {
                "status": "not_found",
                "error": "invalid_direct_question_id",
                "direct_question_id": str(direct_question_id),
            }

        stmt = select(DirectQuestion).where(
            DirectQuestion.id == question_uuid,
            DirectQuestion.tenant_id == tenant_id,
            DirectQuestion.agent_id == agent_id,
            DirectQuestion.is_enabled.is_(True),
        )
        question = (await db.execute(stmt)).scalar_one_or_none()
        if question is None:
            return {
                "status": "not_found",
                "error": "direct_question_not_found",
                "direct_question_id": str(question_uuid),
            }

        safe_content = sanitize_direct_question_content(question.content)
        system_instruction, user_content = split_direct_question_content(safe_content)

        return {
            "status": "ok",
            "direct_question_id": str(question.id),
            "title": question.title,
            "interrupt_dialog": bool(question.interrupt_dialog),
            "notify_telegram": bool(question.notify_telegram),
            "content": user_content,
            "system_instruction": system_instruction,
        }

    _get_direct_answer.__name__ = "get_direct_answer"

    return PydanticTool.from_schema(
        function=_get_direct_answer,
        name="get_direct_answer",
        description=(
            "Data tool: load one curated Q&A / policy card by UUID (same family as the agent's catalog tools—pick by intent). "
            "`direct_question_id` must come from `search_direct_questions` (or a retry after not_found); do not invent ids. "
            "After status=ok: use `content` as facts; keep numbers, addresses, prices, URLs exact. "
            "Apply `system_instruction` if present; call other tools if something is missing."
        ),
        json_schema={
            "type": "object",
            "properties": {
                "direct_question_id": {
                    "type": "string",
                    "description": "UUID of the card (e.g. from search_direct_questions.chosen_candidate_id).",
                }
            },
            "required": ["direct_question_id"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )


def build_direct_questions_search_tool(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    openai_api_key: str | None,
    default_limit: int,
    min_match_percent: int,
    rerank: bool = True,
    analytics_sink: list[dict[str, Any]] | None = None,
) -> PydanticTool:
    async def _search_direct_questions(query: str, limit: int | None = None) -> dict[str, Any]:
        normalized_limit = int(limit) if isinstance(limit, int) else int(default_limit)
        result = await search_direct_question_candidates(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            query=query,
            openai_api_key=openai_api_key,
            limit=max(1, min(normalized_limit, 20)),
            min_match_percent=min_match_percent,
            rerank=rerank,
        )
        if analytics_sink is not None:
            analytics_sink.append(
                {
                    "pipeline_kind": "direct_question",
                    "query": query,
                    "result": result,
                }
            )
        return result

    _search_direct_questions.__name__ = "search_direct_questions"
    return PydanticTool.from_schema(
        function=_search_direct_questions,
        name="search_direct_questions",
        description=(
            "Data tool: semantic search over curated Q&A / policy cards (short fixed answers). "
            "Same idea as catalog tools—one named tool per dataset; this one covers direct-question cards. "
            "Use `search_knowledge_files` for long file-based docs; use other tools for live integrations. "
            "Output may include `chosen_candidate_id` for `get_direct_answer`; do not make up ids."
        ),
        json_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "User intent in natural language."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": default_limit},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )


async def build_knowledge_search_tool(
    *,
    db: AsyncSession,
    tenant_id: UUID,
    agent_id: UUID,
    openai_api_key: str | None,
    description: str | None = None,
) -> PydanticTool | None:
    files_count_stmt = select(KnowledgeFile.id).where(
        KnowledgeFile.tenant_id == tenant_id,
        KnowledgeFile.agent_id == agent_id,
        KnowledgeFile.type == "file",
        KnowledgeFile.is_enabled.is_(True),
    ).limit(1)
    has_files = (await db.execute(files_count_stmt)).first() is not None
    if not has_files:
        return None

    async def _search_knowledge_files(query: str, limit: int = 5) -> dict[str, Any]:
        normalized_limit = max(1, min(int(limit or 5), 10))
        rows = await search_indexed_knowledge_files(
            db,
            tenant_id=tenant_id,
            agent_id=agent_id,
            query=query,
            openai_api_key=openai_api_key,
            limit=normalized_limit,
        )
        results: list[dict[str, Any]] = []
        for row in rows:
            content = str(row.get("content") or "")
            excerpt = content[:900]
            if len(content) > 900:
                excerpt += "..."
            chunk_id = row.get("id")
            results.append(
                {
                    "chunk_id": chunk_id,
                    "file_id": row.get("file_id"),
                    "chunk_index": row.get("chunk_index"),
                    "id": chunk_id,
                    "title": row.get("title"),
                    "meta_tags": row.get("meta_tags") or [],
                    "relevance": row.get("relevance"),
                    "excerpt": excerpt,
                }
            )
        return {"status": "ok", "results": results}

    _search_knowledge_files.__name__ = "search_knowledge_files"
    tool_description = (description or "").strip() or DEFAULT_KNOWLEDGE_SEARCH_TOOL_DESCRIPTION

    return PydanticTool.from_schema(
        function=_search_knowledge_files,
        name="search_knowledge_files",
        description=tool_description,
        json_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language question or search phrase.",
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                    "description": "Maximum number of returned fragments.",
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        takes_ctx=False,
    )


async def build_directory_runtime_tools(
    *,
    db: AsyncSession,
    agent_id: UUID,
    openai_api_key: str | None,
) -> list[PydanticTool]:
    """По одному data-tool на справочник (как и прямые вопросы — обычные тулы агента, имя/описание из настроек)."""
    from app.db.session import async_session_factory
    from app.services.directory.service import get_agent_directory_tools

    specs = await get_agent_directory_tools(
        db,
        agent_id,
        async_session_factory,
        openai_api_key=openai_api_key,
    )
    out: list[PydanticTool] = []
    for spec in specs:
        fn = spec["function"]
        if not callable(fn):
            continue
        # Описание самого тула для LLM — из БД (directory.tool_description), см. create_directory_tool.
        # Ниже только схема единственного параметра; без второго «описания каталога» из кода.
        out.append(
            PydanticTool.from_schema(
                function=fn,
                name=str(spec["name"]),
                description=str(spec.get("description") or spec["name"]),
                json_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language search query.",
                        }
                    },
                    "required": [],
                    "additionalProperties": False,
                },
                takes_ctx=False,
            )
        )
    return out


