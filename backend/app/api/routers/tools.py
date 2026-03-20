from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_or_404, require_scope
from app.db.models.agent import Agent
from app.db.models.binding import AgentToolBinding
from app.db.models.tool import Tool
from app.db.models.tool_parameter import ToolParameter
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.tool import ToolCreate, ToolRead, ToolUpdate, ToolTestRequest, ToolTestResponse
from app.schemas.tool_parameter import (
    ToolParameterRead,
    ToolParametersPreviewRequest,
    ToolParametersPreviewResponse,
    ToolParametersResponse,
    ToolParametersUpdateRequest,
)
from app.services.audit import write_audit
from app.services.tool_parameter_compiler import compile_parameters_to_schema

router = APIRouter()


def _to_parameter_type(schema_type: object) -> str:
    if schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    return "text"


def _parameters_from_input_schema(tool: Tool) -> list[ToolParameterRead]:
    schema = tool.input_schema if isinstance(tool.input_schema, dict) else {}
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        return []
    required_set = set(schema.get("required", []) or [])
    now = datetime.utcnow()
    derived: list[ToolParameterRead] = []
    for index, (name, prop) in enumerate(properties.items()):
        if not isinstance(name, str):
            continue
        prop_dict = prop if isinstance(prop, dict) else {}
        enum_values = prop_dict.get("enum")
        normalized_enum = [str(item) for item in enum_values] if isinstance(enum_values, list) else None
        derived.append(
            ToolParameterRead(
                id=uuid4(),
                tenant_id=tool.tenant_id,
                tool_id=tool.id,
                name=name,
                type=_to_parameter_type(prop_dict.get("type")),
                instruction=str(prop_dict.get("description") or f"Parameter '{name}'"),
                required=name in required_set,
                is_optional=name not in required_set,
                enum_values=normalized_enum,
                x_from_ai=bool(prop_dict.get("x-fromAI", True)),
                default_value=prop_dict.get("default"),
                order_index=index,
                created_at=now,
                updated_at=tool.updated_at,
            )
        )
    return derived


def _validate_tool_payload(payload: ToolCreate | ToolUpdate) -> None:
    if payload.execution_type == "http_webhook":
        if not payload.endpoint:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="endpoint required for http_webhook")
    
    # Валидация parameter_mapping
    if getattr(payload, "parameter_mapping", None):
        valid_targets = {"path", "query", "body", "header"}
        for param, target in payload.parameter_mapping.items():
            if target not in valid_targets:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid parameter target '{target}' for '{param}'. Must be one of: {valid_targets}"
                )
    
    # Валидация response_transform
    if getattr(payload, "response_transform", None):
        mode = payload.response_transform.get("mode")
        if mode not in ("fields", "jmespath", None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="response_transform.mode must be 'fields' or 'jmespath'"
            )
    
    if getattr(payload, "input_schema", None) is not None:
        if not isinstance(payload.input_schema, dict):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="input_schema must be object")
        schema_type = payload.input_schema.get("type")
        if schema_type != "object":
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="input_schema.type must be object")
        properties = payload.input_schema.get("properties", {})
        if any(not str(name).isidentifier() for name in properties):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="input_schema property names must be valid identifiers",
            )


@router.post("", response_model=ToolRead, status_code=status.HTTP_201_CREATED)
async def create_tool(
    payload: ToolCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(get_current_user),
) -> ToolRead:
    _validate_tool_payload(payload)
    if payload.agent_id is not None:
        await get_or_404(
            db,
            Agent,
            id=payload.agent_id,
            tenant_id=user.tenant_id,
            label="Agent",
            extra_where=[Agent.is_deleted.is_(False)],
        )
    tool = Tool(
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
        input_schema=payload.input_schema,
        execution_type=payload.execution_type,
        endpoint=payload.endpoint,
        http_method=payload.http_method,
        auth_type=payload.auth_type,
        status=payload.status,
        webhook_scope=payload.webhook_scope,
        version=payload.version,
        custom_headers=payload.custom_headers,
        response_transform=payload.response_transform,
        parameter_mapping=payload.parameter_mapping,
    )
    db.add(tool)
    try:
        await db.flush()
        if payload.agent_id is not None:
            binding = AgentToolBinding(
                tenant_id=user.tenant_id,
                agent_id=payload.agent_id,
                tool_id=tool.id,
                permission_scope="read",
            )
            db.add(binding)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tool name already exists") from exc
    await db.refresh(tool)
    await write_audit(db, user, "tool.create", "tool", str(tool.id))
    return ToolRead.model_validate(tool)


@router.get("", response_model=list[ToolRead])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("tools:read")),
    limit: int = 50,
    offset: int = 0,
) -> list[ToolRead]:
    stmt = (
        select(Tool)
        .where(Tool.tenant_id == user.tenant_id, Tool.is_deleted.is_(False))
        .order_by(Tool.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    tools = result.scalars().all()
    return [ToolRead.model_validate(tool) for tool in tools]


@router.get("/{tool_id}", response_model=ToolRead)
async def get_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("tools:read")),
) -> ToolRead:
    tool = await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    return ToolRead.model_validate(tool)


@router.put("/{tool_id}", response_model=ToolRead)
async def update_tool(
    tool_id: UUID,
    payload: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("tools:write")),
) -> ToolRead:
    tool = await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )

    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        resolved_execution_type = update_data.get("execution_type", tool.execution_type)
        resolved_endpoint = update_data.get("endpoint", tool.endpoint)
        resolved_input_schema = update_data.get("input_schema", tool.input_schema)
        _validate_tool_payload(
            ToolUpdate(
                execution_type=resolved_execution_type,
                endpoint=resolved_endpoint,
                input_schema=resolved_input_schema,
            )
        )
    for key, value in update_data.items():
        setattr(tool, key, value)
    await db.commit()
    await db.refresh(tool)
    await write_audit(db, user, "tool.update", "tool", str(tool.id))
    return ToolRead.model_validate(tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("tools:write")),
) -> None:
    tool = await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )

    tool.is_deleted = True
    tool.deleted_at = datetime.utcnow()
    await db.commit()
    await write_audit(db, user, "tool.delete", "tool", str(tool.id))
    return None


@router.post(
    "/test",
    response_model=ToolTestResponse,
    summary="Тестовый вызов HTTP tool",
    description="""
Протестировать HTTP tool БЕЗ сохранения в БД.
Используется в конструкторе tool для проверки корректности настроек.

Возвращает:
- Полный ответ от API (raw_body)
- Отфильтрованный ответ (transformed_body, если указан response_transform)
- Метрики (latency, размер, экономия токенов)
- Итоговый URL с подставленными параметрами
    """,
    responses={
        200: {
            "description": "Успешный тестовый вызов",
            "content": {
                "application/json": {
                    "example": {
                        "status_code": 200,
                        "latency_ms": 142,
                        "response_headers": {"content-type": "application/json"},
                        "raw_body": {"login": "torvalds", "name": "Linus Torvalds", "id": 1024025},
                        "transformed_body": {"username": "torvalds", "full_name": "Linus Torvalds"},
                        "raw_size_bytes": 2500,
                        "transformed_size_bytes": 180,
                        "error": None,
                        "request_url": "https://api.github.com/users/torvalds",
                        "request_method": "GET"
                    }
                }
            }
        }
    }
)
async def test_tool_inline(
    payload: ToolTestRequest,
    user: AuthContext = Depends(require_scope("tools:write")),
    db: AsyncSession = Depends(get_db),
) -> ToolTestResponse:
    """Тестовый вызов tool без сохранения (для конструктора)."""
    from app.services.tool_executor import execute_tool_test
    from app.services.credentials import decrypt_config
    
    if not payload.endpoint:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="endpoint is required")
    
    # Загрузить и расшифровать credential если указан
    secret_payload = None
    if payload.credential_id:
        from app.db.models.credential import Credential
        stmt = select(Credential).where(
            Credential.id == payload.credential_id,
            Credential.tenant_id == user.tenant_id,
            Credential.is_active.is_(True),
        )
        result = await db.execute(stmt)
        credential = result.scalar_one_or_none()
        if credential:
            try:
                secret_payload = decrypt_config(credential.config)
            except ValueError:
                pass
    
    result = await execute_tool_test(
        endpoint=payload.endpoint,
        args=payload.args,
        http_method=payload.http_method,
        parameter_mapping=payload.parameter_mapping,
        auth_type=payload.auth_type,
        secret_payload=secret_payload,
        custom_headers=payload.custom_headers,
        response_transform=payload.response_transform,
    )
    return ToolTestResponse(**result)


@router.post(
    "/{tool_id}/test",
    response_model=ToolTestResponse,
    summary="Тестовый вызов сохранённого tool",
    description="""
Протестировать уже сохранённый HTTP tool.
Использует конфигурацию из БД (endpoint, http_method, parameter_mapping).

Позволяет переопределить:
- response_transform (протестировать другой фильтр)
- credential_id (использовать другой credential)
    """,
)
async def test_tool_saved(
    tool_id: UUID,
    payload: ToolTestRequest,
    user: AuthContext = Depends(require_scope("tools:read")),
    db: AsyncSession = Depends(get_db),
) -> ToolTestResponse:
    """Тестовый вызов сохранённого tool."""
    from app.services.tool_executor import execute_tool_test
    from app.services.credentials import decrypt_config
    
    # Загрузить tool
    tool = await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    
    if not tool.endpoint:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool has no endpoint")
    
    # Загрузить credential (можно из payload или дефолтный из binding)
    secret_payload = None
    credential_id = payload.credential_id
    
    if credential_id:
        from app.db.models.credential import Credential
        stmt = select(Credential).where(
            Credential.id == credential_id,
            Credential.tenant_id == user.tenant_id,
            Credential.is_active.is_(True),
        )
        result_cred = await db.execute(stmt)
        credential = result_cred.scalar_one_or_none()
        if credential:
            try:
                secret_payload = decrypt_config(credential.config)
            except ValueError:
                pass
    
    result = await execute_tool_test(
        endpoint=tool.endpoint,
        args=payload.args,
        http_method=tool.http_method or "POST",
        parameter_mapping=payload.parameter_mapping or tool.parameter_mapping,
        auth_type=tool.auth_type,
        secret_payload=secret_payload,
        custom_headers=payload.custom_headers,
        response_transform=payload.response_transform or tool.response_transform,
    )
    return ToolTestResponse(**result)


@router.get("/{tool_id}/parameters", response_model=ToolParametersResponse)
async def get_tool_parameters(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("tools:read")),
) -> ToolParametersResponse:
    tool = await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    stmt = (
        select(ToolParameter)
        .where(ToolParameter.tool_id == tool_id, ToolParameter.tenant_id == user.tenant_id)
        .order_by(ToolParameter.order_index.asc(), ToolParameter.created_at.asc())
    )
    parameters = (await db.execute(stmt)).scalars().all()
    if parameters:
        response_parameters = [ToolParameterRead.model_validate(item) for item in parameters]
    else:
        # Backward compatibility: legacy tools may have only input_schema without tool_parameters rows.
        response_parameters = _parameters_from_input_schema(tool)
    generated_schema = compile_parameters_to_schema([item.model_dump() for item in response_parameters])
    return ToolParametersResponse(
        tool_id=tool_id,
        parameters=response_parameters,
        generated_input_schema=generated_schema,
    )


@router.put("/{tool_id}/parameters", response_model=ToolParametersResponse)
async def update_tool_parameters(
    tool_id: UUID,
    payload: ToolParametersUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("tools:write")),
) -> ToolParametersResponse:
    tool = await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    schema = compile_parameters_to_schema(payload.parameters)

    stmt = select(ToolParameter).where(ToolParameter.tool_id == tool_id, ToolParameter.tenant_id == user.tenant_id)
    existing = (await db.execute(stmt)).scalars().all()
    for item in existing:
        await db.delete(item)
    await db.flush()

    new_parameters: list[ToolParameter] = []
    for item in payload.parameters:
        parameter = ToolParameter(
            tenant_id=user.tenant_id,
            tool_id=tool_id,
            name=item.name,
            type=item.type,
            instruction=item.instruction,
            required=item.required,
            is_optional=item.is_optional,
            enum_values=item.enum_values,
            x_from_ai=item.x_from_ai,
            default_value=item.default_value,
            order_index=item.order_index,
        )
        db.add(parameter)
        new_parameters.append(parameter)

    tool.input_schema = schema
    await db.commit()
    for item in new_parameters:
        await db.refresh(item)
    await db.refresh(tool)
    await write_audit(db, user, "tool.parameters.update", "tool", str(tool.id))

    return ToolParametersResponse(
        tool_id=tool_id,
        parameters=[ToolParameterRead.model_validate(item) for item in new_parameters],
        generated_input_schema=schema,
    )


@router.post("/parameters/preview-schema", response_model=ToolParametersPreviewResponse)
async def preview_parameters_schema(
    payload: ToolParametersPreviewRequest,
    user: AuthContext = Depends(require_scope("tools:read")),
) -> ToolParametersPreviewResponse:
    _ = user
    schema = compile_parameters_to_schema(payload.parameters)
    return ToolParametersPreviewResponse(input_schema=schema)
