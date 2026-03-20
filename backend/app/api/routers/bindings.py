from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
from uuid import uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_or_404, require_scope
from app.db.models.agent import Agent
from app.db.models.binding import AgentToolBinding
from app.db.models.function_rule import FunctionRule
from app.db.models.knowledge_file import KnowledgeFile
from app.db.session import get_db
from app.db.models.tool import Tool
from app.db.models.credential import Credential
from app.schemas.auth import AuthContext
from app.schemas.binding import BindingCreate, BindingRead, BindingWithToolRead, ToolWithParametersRead
from app.services.audit import write_audit
from app.services.runtime.tools import DEFAULT_KNOWLEDGE_SEARCH_TOOL_DESCRIPTION

router = APIRouter()


def _build_virtual_knowledge_binding(
    *,
    tenant_id: UUID,
    agent_id: UUID,
    description: str | None,
) -> BindingWithToolRead:
    """Build a synthetic binding entry for runtime knowledge files tool."""
    now = datetime.now(timezone.utc)
    virtual_tool_id = uuid5(NAMESPACE_URL, f"knowledge-search-tool:{agent_id}")
    virtual_binding_id = uuid5(NAMESPACE_URL, f"knowledge-search-binding:{agent_id}")
    tool_description = (description or "").strip() or DEFAULT_KNOWLEDGE_SEARCH_TOOL_DESCRIPTION
    input_schema = {
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
    }
    return BindingWithToolRead(
        id=virtual_binding_id,
        tenant_id=tenant_id,
        agent_id=agent_id,
        tool_id=virtual_tool_id,
        permission_scope="read",
        timeout_ms=None,
        rate_limit=None,
        allowed_domains=None,
        secrets_ref=None,
        credential_id=None,
        created_at=now,
        updated_at=None,
        tool=ToolWithParametersRead(
            id=virtual_tool_id,
            tenant_id=tenant_id,
            name="search_knowledge_files",
            description=tool_description,
            input_schema=input_schema,
            execution_type="internal",
            endpoint=None,
            http_method="POST",
            auth_type="none",
            status="active",
            webhook_scope="tool",
            version=1,
            custom_headers=None,
            response_transform=None,
            parameter_mapping=None,
            created_at=now,
            updated_at=None,
            parameters=[],
        ),
    )


@router.post("/{agent_id}/tools/{tool_id}", response_model=BindingRead, status_code=status.HTTP_201_CREATED)
async def bind_tool(
    agent_id: UUID,
    tool_id: UUID,
    payload: BindingCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> BindingRead:
    await get_or_404(
        db, Agent, id=agent_id, tenant_id=user.tenant_id, label="Agent",
        extra_where=[Agent.is_deleted.is_(False)],
    )
    await get_or_404(
        db, Tool, id=tool_id, tenant_id=user.tenant_id, label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )

    if payload.secrets_ref and payload.credential_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either secrets_ref or credential_id",
        )

    credential_id = None
    if payload.credential_id:
        credential = await get_or_404(
            db, Credential, id=payload.credential_id, tenant_id=user.tenant_id, label="Credential",
            extra_where=[Credential.is_active.is_(True)],
        )
        credential_id = credential.id

    binding = AgentToolBinding(
        tenant_id=user.tenant_id,
        agent_id=agent_id,
        tool_id=tool_id,
        credential_id=credential_id,
        permission_scope=payload.permission_scope,
        timeout_ms=payload.timeout_ms,
        rate_limit=payload.rate_limit,
        allowed_domains=payload.allowed_domains,
        secrets_ref=payload.secrets_ref,
    )
    db.add(binding)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Binding already exists") from exc
    await db.refresh(binding)
    await write_audit(db, user, "binding.create", "binding", str(binding.id))
    return BindingRead.model_validate(binding)


@router.get("/{agent_id}/tools", response_model=list[BindingRead])
async def list_bindings(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[BindingRead]:
    """
    Получить список bindings для агента (только IDs и настройки привязки).
    
    Для получения полной информации о tools используйте /agents/{agent_id}/tools/details
    """
    stmt = select(AgentToolBinding).where(
        AgentToolBinding.agent_id == agent_id,
        AgentToolBinding.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    bindings = result.scalars().all()
    return [BindingRead.model_validate(binding) for binding in bindings]


@router.get("/{agent_id}/tools/details", response_model=list[BindingWithToolRead])
async def list_bindings_with_tools(
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(get_current_user),
) -> list[BindingWithToolRead]:
    """
    Получить список bindings с полной информацией о tools.

    Возвращает каждый binding вместе с полными данными tool, включая:
    - name, description
    - endpoint, http_method
    - parameter_mapping
    - response_transform
    - input_schema

    Это позволяет фронтенду получить все нужные данные одним запросом.
    """
    agent = await get_or_404(
        db,
        Agent,
        id=agent_id,
        tenant_id=user.tenant_id,
        label="Agent",
        extra_where=[Agent.is_deleted.is_(False)],
    )

    stmt = (
        select(AgentToolBinding)
        .options(selectinload(AgentToolBinding.tool).selectinload(Tool.parameters))
        .where(
            AgentToolBinding.agent_id == agent_id,
            AgentToolBinding.tenant_id == user.tenant_id,
        )
    )
    result = await db.execute(stmt)
    bindings = result.scalars().all()

    linked_internal_tool_ids = {
        row[0]
        for row in (
            await db.execute(
                select(FunctionRule.tool_id).where(
                    FunctionRule.tenant_id == user.tenant_id,
                    FunctionRule.agent_id == agent_id,
                    FunctionRule.tool_id.is_not(None),
                    FunctionRule.enabled.is_(True),
                )
            )
        ).all()
    }

    enriched = []
    for binding in bindings:
        if binding.tool and binding.tool.status != "active":
            # Do not expose disabled/deprecated tools in runtime/system-prompt side panels.
            continue
        if (
            binding.tool
            and binding.tool.execution_type == "internal"
            and binding.tool.id not in linked_internal_tool_ids
        ):
            # Hide orphan internal tools that are no longer referenced by any function rule.
            continue
        binding_data = BindingRead.model_validate(binding).model_dump()
        tool_data = None
        if binding.tool and not binding.tool.is_deleted:
            tool_data = ToolWithParametersRead.model_validate(binding.tool)
        enriched.append(BindingWithToolRead(**binding_data, tool=tool_data))

    # Expose runtime-only knowledge files search tool in the same registry used by
    # "Системный промпт" UI to avoid hidden capabilities mismatch.
    has_knowledge_files_stmt = select(
        exists().where(
            KnowledgeFile.tenant_id == user.tenant_id,
            KnowledgeFile.agent_id == agent_id,
            KnowledgeFile.type == "file",
            KnowledgeFile.is_enabled.is_(True),
        )
    )
    has_knowledge_files = bool((await db.execute(has_knowledge_files_stmt)).scalar())
    already_present = any(
        item.tool is not None and item.tool.name == "search_knowledge_files"
        for item in enriched
    )
    if has_knowledge_files and not already_present:
        enriched.append(
            _build_virtual_knowledge_binding(
                tenant_id=user.tenant_id,
                agent_id=agent_id,
                description=agent.knowledge_tool_description,
            )
        )

    return enriched


@router.delete("/{agent_id}/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unbind_tool(
    agent_id: UUID,
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    stmt = select(AgentToolBinding).where(
        AgentToolBinding.agent_id == agent_id,
        AgentToolBinding.tool_id == tool_id,
        AgentToolBinding.tenant_id == user.tenant_id,
    )
    result = await db.execute(stmt)
    binding = result.scalar_one_or_none()
    if binding is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Binding not found")

    tool = await get_or_404(
        db,
        Tool,
        id=binding.tool_id,
        tenant_id=user.tenant_id,
        label="Tool",
        extra_where=[Tool.is_deleted.is_(False)],
    )
    await db.delete(binding)

    deleted_tool_id: UUID | None = None
    if tool is not None and not tool.is_deleted and tool.execution_type == "internal":
        remaining_binding_stmt = select(AgentToolBinding.id).where(
            AgentToolBinding.tenant_id == user.tenant_id,
            AgentToolBinding.tool_id == tool.id,
        )
        remaining_binding = (await db.execute(remaining_binding_stmt)).scalar_one_or_none()
        if remaining_binding is None:
            linked_rule_stmt = select(FunctionRule.id).where(
                FunctionRule.tenant_id == user.tenant_id,
                FunctionRule.tool_id == tool.id,
            )
            linked_rule = (await db.execute(linked_rule_stmt)).scalar_one_or_none()
            if linked_rule is None:
                tool.is_deleted = True
                tool.deleted_at = datetime.now(timezone.utc)
                deleted_tool_id = tool.id

    await db.commit()
    await write_audit(db, user, "binding.delete", "binding", str(binding.id))
    if deleted_tool_id is not None:
        await write_audit(db, user, "tool.delete", "tool", str(deleted_tool_id))
    return None
