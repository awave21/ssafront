from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import require_scope
from app.db.models.user_table import UserTable, UserTableAttribute, UserTableRecord
from app.db.session import get_db
from app.schemas.auth import AuthContext
from app.schemas.user_table import (
    UserTableAttributeCreate,
    UserTableAttributeRead,
    UserTableAttributeReorder,
    UserTableAttributeUpdate,
    UserTableCreate,
    UserTableListItem,
    UserTableRead,
    UserTableRecordCreate,
    UserTableRecordRead,
    UserTableRecordsBulkCreate,
    UserTableRecordsBulkCreateResponse,
    UserTableRecordsListResponse,
    UserTableRecordUpdate,
    UserTableUpdate,
)
from app.services.user_table.service import get_table_or_none, validate_record_data

router = APIRouter()

MAX_TABLES_PER_TENANT = 100
MAX_ATTRIBUTES_PER_TABLE = 100
SYSTEM_ID_FIELD_NAME = "id"
SYSTEM_CREATED_AT_FIELD_NAME = "created_at"
SYSTEM_FIELD_NAMES = {SYSTEM_ID_FIELD_NAME, SYSTEM_CREATED_AT_FIELD_NAME}

_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


async def _rename_record_data_key_for_attribute(
    db: AsyncSession,
    *,
    table_id: UUID,
    tenant_id: UUID,
    old_key: str,
    new_key: str,
) -> None:
    """Переносит значение ключа old_key → new_key в JSONB data всех записей таблицы."""
    if old_key == new_key:
        return
    if not _SLUG_RE.match(old_key) or not _SLUG_RE.match(new_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid attribute slug for data migration",
        )
    await db.execute(
        text(
            f"""
            UPDATE user_table_records
            SET data = CASE
                WHEN data ? '{old_key}' THEN (data - '{old_key}') || jsonb_build_object('{new_key}', data->'{old_key}')
                ELSE data
            END
            WHERE table_id = CAST(:tid AS uuid)
              AND tenant_id = CAST(:ten AS uuid)
              AND is_deleted = false
            """
        ),
        {"tid": str(table_id), "ten": str(tenant_id)},
    )


async def _get_table_or_404(db: AsyncSession, *, tenant_id: UUID, table_id: UUID) -> UserTable:
    table = await get_table_or_none(db, table_id=table_id, tenant_id=tenant_id)
    if table is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Table not found")
    return table


def _build_table_attributes(payload_attrs: list[UserTableAttributeCreate]) -> list[UserTableAttributeCreate]:
    # System fields are always present and managed by backend.
    non_system_attrs = [attr for attr in payload_attrs if attr.name not in SYSTEM_FIELD_NAMES]
    system_id_attr = UserTableAttributeCreate(
        name=SYSTEM_ID_FIELD_NAME,
        label="ID",
        attribute_type="integer",
        type_config={},
        is_required=True,
        is_searchable=False,
        is_unique=True,
        order_index=0,
        default_value=None,
    )
    system_created_at_attr = UserTableAttributeCreate(
        name=SYSTEM_CREATED_AT_FIELD_NAME,
        label="Дата создания",
        attribute_type="timestamp",
        type_config={},
        is_required=True,
        is_searchable=False,
        is_unique=False,
        order_index=0,
        default_value=None,
    )
    return [system_id_attr, system_created_at_attr, *non_system_attrs]


@router.get("/tables", response_model=list[UserTableListItem])
async def list_tables(
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> list[UserTableListItem]:
    stmt = (
        select(UserTable)
        .options(selectinload(UserTable.attributes))
        .where(
            UserTable.tenant_id == user.tenant_id,
            UserTable.is_deleted.is_(False),
        )
        .order_by(UserTable.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        UserTableListItem(
            id=item.id,
            name=item.name,
            description=item.description,
            records_count=item.records_count,
            attributes_count=len(item.attributes),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in rows
    ]


@router.post("/tables", response_model=UserTableRead, status_code=status.HTTP_201_CREATED)
async def create_table(
    payload: UserTableCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableRead:
    count_stmt = select(func.count(UserTable.id)).where(
        UserTable.tenant_id == user.tenant_id,
        UserTable.is_deleted.is_(False),
    )
    total_tables = (await db.execute(count_stmt)).scalar_one()
    if total_tables >= MAX_TABLES_PER_TENANT:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tables limit reached")

    table = UserTable(
        tenant_id=user.tenant_id,
        name=payload.name,
        description=payload.description,
    )
    db.add(table)
    await db.flush()

    table_attributes = _build_table_attributes(payload.attributes)
    for index, attr in enumerate(table_attributes):
        db.add(
            UserTableAttribute(
                tenant_id=user.tenant_id,
                table_id=table.id,
                name=attr.name,
                label=attr.label,
                attribute_type=attr.attribute_type,
                type_config=attr.type_config,
                is_required=attr.is_required,
                is_searchable=attr.is_searchable,
                is_unique=attr.is_unique,
                order_index=index,
                default_value=attr.default_value,
            )
        )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Failed to create table") from exc

    created = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table.id)
    return UserTableRead.model_validate(created)


@router.get("/tables/{table_id}", response_model=UserTableRead)
async def get_table(
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> UserTableRead:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    return UserTableRead.model_validate(table)


@router.patch("/tables/{table_id}", response_model=UserTableRead)
async def update_table(
    table_id: UUID,
    payload: UserTableUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableRead:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(table, key, value)
    await db.commit()
    await db.refresh(table)
    return UserTableRead.model_validate(table)


@router.delete("/tables/{table_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_table(
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    table.is_deleted = True
    table.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/tables/{table_id}/attributes", response_model=list[UserTableAttributeRead])
async def list_attributes(
    table_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> list[UserTableAttributeRead]:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    return [UserTableAttributeRead.model_validate(item) for item in table.attributes]


@router.post("/tables/{table_id}/attributes", response_model=UserTableAttributeRead, status_code=status.HTTP_201_CREATED)
async def create_attribute(
    table_id: UUID,
    payload: UserTableAttributeCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableAttributeRead:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    if len(table.attributes) >= MAX_ATTRIBUTES_PER_TABLE:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Attributes limit reached")
    if payload.name in SYSTEM_FIELD_NAMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{payload.name} is a reserved system field",
        )
    attr = UserTableAttribute(
        tenant_id=user.tenant_id,
        table_id=table.id,
        name=payload.name,
        label=payload.label,
        attribute_type=payload.attribute_type,
        type_config=payload.type_config,
        is_required=payload.is_required,
        is_searchable=payload.is_searchable,
        is_unique=payload.is_unique,
        order_index=payload.order_index,
        default_value=payload.default_value,
    )
    db.add(attr)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Attribute already exists") from exc
    await db.refresh(attr)
    return UserTableAttributeRead.model_validate(attr)


@router.patch("/tables/{table_id}/attributes/{attribute_id}", response_model=UserTableAttributeRead)
async def update_attribute(
    table_id: UUID,
    attribute_id: UUID,
    payload: UserTableAttributeUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableAttributeRead:
    await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    stmt = select(UserTableAttribute).where(
        UserTableAttribute.id == attribute_id,
        UserTableAttribute.table_id == table_id,
        UserTableAttribute.tenant_id == user.tenant_id,
    )
    attr = (await db.execute(stmt)).scalar_one_or_none()
    if attr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")
    if attr.name in SYSTEM_FIELD_NAMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"System field {attr.name} cannot be updated",
        )
    data = payload.model_dump(exclude_unset=True)
    merged_name = data.get("name", attr.name)

    if "name" in data and data["name"] != attr.name:
        new_name = data["name"]
        if new_name in SYSTEM_FIELD_NAMES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Name '{new_name}' is reserved for system fields",
            )
        dup_stmt = select(UserTableAttribute.id).where(
            UserTableAttribute.table_id == table_id,
            UserTableAttribute.tenant_id == user.tenant_id,
            UserTableAttribute.name == new_name,
            UserTableAttribute.id != attribute_id,
        )
        if (await db.execute(dup_stmt.limit(1))).scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An attribute with this code already exists in the table",
            )
        await _rename_record_data_key_for_attribute(
            db,
            table_id=table_id,
            tenant_id=user.tenant_id,
            old_key=attr.name,
            new_key=new_name,
        )

    for key, value in data.items():
        setattr(attr, key, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not update attribute (duplicate code or constraint violation)",
        ) from exc
    await db.refresh(attr)
    return UserTableAttributeRead.model_validate(attr)


@router.delete("/tables/{table_id}/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attribute(
    table_id: UUID,
    attribute_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    stmt = select(UserTableAttribute).where(
        UserTableAttribute.id == attribute_id,
        UserTableAttribute.table_id == table_id,
        UserTableAttribute.tenant_id == user.tenant_id,
    )
    attr = (await db.execute(stmt)).scalar_one_or_none()
    if attr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attribute not found")
    if attr.name in SYSTEM_FIELD_NAMES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"System field {attr.name} cannot be deleted",
        )
    await db.delete(attr)
    await db.commit()


@router.post("/tables/{table_id}/attributes/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_attributes(
    table_id: UUID,
    payload: UserTableAttributeReorder,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    mapping = {item.id: item for item in table.attributes}
    for index, attr_id in enumerate(payload.attribute_ids):
        if attr_id in mapping:
            mapping[attr_id].order_index = index
    await db.commit()


@router.get("/tables/{table_id}/records", response_model=UserTableRecordsListResponse)
async def list_records(
    table_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:read")),
) -> UserTableRecordsListResponse:
    await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    total_stmt = select(func.count(UserTableRecord.id)).where(
        UserTableRecord.table_id == table_id,
        UserTableRecord.tenant_id == user.tenant_id,
        UserTableRecord.is_deleted.is_(False),
    )
    total = (await db.execute(total_stmt)).scalar_one()
    stmt = (
        select(UserTableRecord)
        .where(
            UserTableRecord.table_id == table_id,
            UserTableRecord.tenant_id == user.tenant_id,
            UserTableRecord.is_deleted.is_(False),
        )
        .order_by(UserTableRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    records = (await db.execute(stmt)).scalars().all()
    return UserTableRecordsListResponse(
        items=[UserTableRecordRead.model_validate(item) for item in records],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/tables/{table_id}/records", response_model=UserTableRecordRead, status_code=status.HTTP_201_CREATED)
async def create_record(
    table_id: UUID,
    payload: UserTableRecordCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableRecordRead:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    record_data = dict(payload.data)
    record_data[SYSTEM_ID_FIELD_NAME] = table.next_row_id
    record_data.setdefault(SYSTEM_CREATED_AT_FIELD_NAME, datetime.now(timezone.utc).isoformat())
    errors = await validate_record_data(db, table=table, data=record_data)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
    table.next_row_id += 1
    record = UserTableRecord(
        tenant_id=user.tenant_id,
        table_id=table.id,
        data=record_data,
        source=payload.source,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return UserTableRecordRead.model_validate(record)


@router.post("/tables/{table_id}/records/bulk", response_model=UserTableRecordsBulkCreateResponse, status_code=status.HTTP_201_CREATED)
async def bulk_create_records(
    table_id: UUID,
    payload: UserTableRecordsBulkCreate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableRecordsBulkCreateResponse:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    created = 0
    failed = 0
    errors: list[dict[str, object]] = []
    next_row_id = table.next_row_id
    for index, row_data in enumerate(payload.records):
        prepared_row_data = dict(row_data)
        prepared_row_data[SYSTEM_ID_FIELD_NAME] = next_row_id
        prepared_row_data.setdefault(SYSTEM_CREATED_AT_FIELD_NAME, datetime.now(timezone.utc).isoformat())
        row_errors = await validate_record_data(db, table=table, data=prepared_row_data)
        if row_errors:
            failed += 1
            errors.append({"index": index, "errors": row_errors})
            continue
        db.add(
            UserTableRecord(
                tenant_id=user.tenant_id,
                table_id=table.id,
                data=prepared_row_data,
                source=payload.source,
            )
        )
        created += 1
        next_row_id += 1
    table.next_row_id = next_row_id
    await db.commit()
    return UserTableRecordsBulkCreateResponse(
        created=created,
        failed=failed,
        errors=errors,
    )


@router.patch("/tables/{table_id}/records/{record_id}", response_model=UserTableRecordRead)
async def update_record(
    table_id: UUID,
    record_id: UUID,
    payload: UserTableRecordUpdate,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> UserTableRecordRead:
    table = await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    stmt = select(UserTableRecord).where(
        UserTableRecord.id == record_id,
        UserTableRecord.table_id == table_id,
        UserTableRecord.tenant_id == user.tenant_id,
        UserTableRecord.is_deleted.is_(False),
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    updated_data = dict(payload.data)
    if SYSTEM_ID_FIELD_NAME in record.data:
        updated_data[SYSTEM_ID_FIELD_NAME] = record.data[SYSTEM_ID_FIELD_NAME]
    else:
        updated_data[SYSTEM_ID_FIELD_NAME] = table.next_row_id
        table.next_row_id += 1
    if SYSTEM_CREATED_AT_FIELD_NAME in payload.data:
        updated_data[SYSTEM_CREATED_AT_FIELD_NAME] = payload.data[SYSTEM_CREATED_AT_FIELD_NAME]
    elif SYSTEM_CREATED_AT_FIELD_NAME in record.data:
        updated_data[SYSTEM_CREATED_AT_FIELD_NAME] = record.data[SYSTEM_CREATED_AT_FIELD_NAME]
    else:
        updated_data.setdefault(SYSTEM_CREATED_AT_FIELD_NAME, datetime.now(timezone.utc).isoformat())
    errors = await validate_record_data(db, table=table, data=updated_data, ignore_record_id=record.id)
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
    record.data = updated_data
    await db.commit()
    await db.refresh(record)
    return UserTableRecordRead.model_validate(record)


@router.delete("/tables/{table_id}/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_record(
    table_id: UUID,
    record_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: AuthContext = Depends(require_scope("agents:write")),
) -> None:
    await _get_table_or_404(db, tenant_id=user.tenant_id, table_id=table_id)
    stmt = select(UserTableRecord).where(
        UserTableRecord.id == record_id,
        UserTableRecord.table_id == table_id,
        UserTableRecord.tenant_id == user.tenant_id,
        UserTableRecord.is_deleted.is_(False),
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    record.is_deleted = True
    record.deleted_at = datetime.now(timezone.utc)
    await db.commit()
