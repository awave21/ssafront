from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import base64

from app.api.deps import get_current_user, get_or_404, require_scope
from app.db.models.credential import Credential
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.credential import (
    CredentialCreate,
    CredentialRead,
    CredentialTestRequest,
    CredentialTestResponse,
    CredentialUpdate,
)
from app.services.credentials import ENCRYPTED_MARKER, decrypt_config, encrypt_config, mask_config
from app.services.tool_executor import ToolExecutionError, _ensure_allowed_domain
from app.services.audit import write_audit

router = APIRouter()


def _validate_credential_payload(payload: CredentialCreate | CredentialUpdate) -> None:
    auth_type = payload.auth_type
    config = payload.config if hasattr(payload, "config") else None
    if auth_type and auth_type != "none" and config is not None and not config:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="config must be provided for auth_type",
        )

def _mask_or_placeholder(config: dict[str, Any]) -> dict[str, Any]:
    try:
        return mask_config(decrypt_config(config))
    except ValueError:
        return {ENCRYPTED_MARKER: True}


def _apply_auth(
    auth_type: str,
    secret_payload: dict[str, Any],
    headers: dict[str, str],
    params: dict[str, Any],
) -> None:
    if auth_type == "none":
        return
    if auth_type == "api_key":
        header_name = str(secret_payload.get("header") or "x-api-key")
        header_value = secret_payload.get("value")
        if not header_value:
            raise HTTPException(status_code=422, detail="Missing API key value")
        headers[header_name] = str(header_value)
        return
    if auth_type == "bearer_token":
        token = secret_payload.get("token") or secret_payload.get("value")
        if not token:
            raise HTTPException(status_code=422, detail="Missing bearer token value")
        headers["Authorization"] = f"Bearer {token}"
        return
    if auth_type == "basic_auth":
        username = secret_payload.get("username")
        password = secret_payload.get("password")
        if not username or not password:
            raise HTTPException(status_code=422, detail="Missing basic auth username/password")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
        return
    if auth_type == "custom_header":
        headers.update({str(key): str(value) for key, value in secret_payload.items()})
        return
    if auth_type == "query_param":
        param_name = str(secret_payload.get("name") or "api_key")
        param_value = secret_payload.get("value")
        if not param_value:
            raise HTTPException(status_code=422, detail="Missing query param value")
        params[param_name] = param_value
        return
    raise HTTPException(status_code=422, detail=f"auth_type '{auth_type}' is not supported for testing")


@router.post("", response_model=CredentialRead, status_code=status.HTTP_201_CREATED)
async def create_credential(
    payload: CredentialCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> CredentialRead:
    _validate_credential_payload(payload)
    encrypted_config = encrypt_config(payload.config)
    credential = Credential(
        tenant_id=user.tenant_id,
        name=payload.name,
        auth_type=payload.auth_type,
        config=encrypted_config,
        is_active=payload.is_active,
    )
    db.add(credential)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential name already exists") from exc
    await db.refresh(credential)
    await write_audit(db, user, "credential.create", "credential", str(credential.id))
    masked = _mask_or_placeholder(credential.config)
    return CredentialRead.model_validate(credential).model_copy(update={"config": masked})


@router.get("", response_model=list[CredentialRead])
async def list_credentials(
    include_inactive: bool = False,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> list[CredentialRead]:
    stmt = select(Credential).where(Credential.tenant_id == user.tenant_id)
    if not include_inactive:
        stmt = stmt.where(Credential.is_active.is_(True))
    result = await db.execute(stmt.order_by(Credential.created_at.desc()))
    credentials = result.scalars().all()
    response: list[CredentialRead] = []
    for credential in credentials:
        masked = _mask_or_placeholder(credential.config)
        response.append(CredentialRead.model_validate(credential).model_copy(update={"config": masked}))
    return response


@router.get("/{credential_id}", response_model=CredentialRead)
async def get_credential(
    credential_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> CredentialRead:
    credential = await get_or_404(db, Credential, id=credential_id, tenant_id=user.tenant_id, label="Credential")
    masked = _mask_or_placeholder(credential.config)
    return CredentialRead.model_validate(credential).model_copy(update={"config": masked})


@router.put("/{credential_id}", response_model=CredentialRead)
async def update_credential(
    credential_id: UUID,
    payload: CredentialUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> CredentialRead:
    credential = await get_or_404(db, Credential, id=credential_id, tenant_id=user.tenant_id, label="Credential")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data:
        resolved_auth_type = update_data.get("auth_type", credential.auth_type)
        resolved_config = update_data.get("config", credential.config)
        _validate_credential_payload(
            CredentialUpdate(auth_type=resolved_auth_type, config=resolved_config)
        )
    if "config" in update_data:
        update_data["config"] = encrypt_config(update_data["config"])
    for key, value in update_data.items():
        setattr(credential, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential name already exists") from exc
    await db.refresh(credential)
    await write_audit(db, user, "credential.update", "credential", str(credential.id))
    masked = _mask_or_placeholder(credential.config)
    return CredentialRead.model_validate(credential).model_copy(update={"config": masked})


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    credential_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    credential = await get_or_404(db, Credential, id=credential_id, tenant_id=user.tenant_id, label="Credential")
    credential.is_active = False
    await db.commit()
    await write_audit(db, user, "credential.delete", "credential", str(credential.id))
    return None


@router.post("/{credential_id}/test", response_model=CredentialTestResponse)
async def test_credential(
    credential_id: UUID,
    payload: CredentialTestRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> CredentialTestResponse:
    credential = await get_or_404(
        db, Credential, id=credential_id, tenant_id=user.tenant_id, label="Credential",
        extra_where=[Credential.is_active.is_(True)],
    )

    try:
        config = decrypt_config(credential.config)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    headers: dict[str, str] = dict(payload.headers or {})
    params: dict[str, Any] = dict(payload.params or {})

    if payload.allowed_domains:
        try:
            _ensure_allowed_domain(payload.endpoint, payload.allowed_domains)
        except ToolExecutionError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    _apply_auth(credential.auth_type, config, headers, params)

    async with httpx.AsyncClient(timeout=payload.timeout_seconds) as client:
        response = await client.request(
            payload.method,
            payload.endpoint,
            headers=headers,
            params=params or None,
            json=payload.json,
        )

    body = response.text[:2000]
    return CredentialTestResponse(status_code=response.status_code, body=body)
