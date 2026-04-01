from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.user_table import UserTable, UserTableAttribute, UserTableRecord


def _coerce_int(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _coerce_float(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


async def get_table_or_none(db: AsyncSession, *, table_id: UUID, tenant_id: UUID) -> UserTable | None:
    stmt = (
        select(UserTable)
        .options(selectinload(UserTable.attributes))
        .where(
            UserTable.id == table_id,
            UserTable.tenant_id == tenant_id,
            UserTable.is_deleted.is_(False),
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def validate_record_data(
    db: AsyncSession,
    *,
    table: UserTable,
    data: dict[str, Any],
    ignore_record_id: UUID | None = None,
) -> list[str]:
    errors: list[str] = []
    for attr in table.attributes:
        value = data.get(attr.name)
        if value is None:
            if attr.is_required and attr.default_value is None:
                errors.append(f"field '{attr.name}' is required")
            continue

        if attr.attribute_type in {"text", "varchar", "date", "datetime", "timestamp"}:
            if not isinstance(value, str):
                errors.append(f"field '{attr.name}' must be a string")
        if attr.attribute_type == "varchar" and isinstance(value, str):
            max_length = int(attr.type_config.get("max_length", 256))
            if len(value) > max_length:
                errors.append(f"field '{attr.name}' exceeds max length of {max_length}")
        elif attr.attribute_type == "integer":
            if not _coerce_int(value):
                errors.append(f"field '{attr.name}' must be an integer")
        elif attr.attribute_type == "float":
            if not _coerce_float(value):
                errors.append(f"field '{attr.name}' must be a number")
        elif attr.attribute_type == "boolean":
            if not isinstance(value, bool):
                errors.append(f"field '{attr.name}' must be boolean")
        elif attr.attribute_type == "text_array":
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"field '{attr.name}' must be an array of strings")
        elif attr.attribute_type == "number_array":
            if not isinstance(value, list) or not all(_coerce_float(item) for item in value):
                errors.append(f"field '{attr.name}' must be an array of numbers")
        elif attr.attribute_type == "json":
            if not isinstance(value, (dict, list, str, int, float, bool)) and value is not None:
                errors.append(f"field '{attr.name}' must be valid JSON value")

        if attr.is_unique:
            value_text = str(value)
            uniqueness_stmt = select(UserTableRecord.id).where(
                UserTableRecord.table_id == table.id,
                UserTableRecord.tenant_id == table.tenant_id,
                UserTableRecord.is_deleted.is_(False),
                UserTableRecord.data[attr.name].astext == value_text,
            )
            if ignore_record_id is not None:
                uniqueness_stmt = uniqueness_stmt.where(UserTableRecord.id != ignore_record_id)
            duplicate = (await db.execute(uniqueness_stmt.limit(1))).scalar_one_or_none()
            if duplicate is not None:
                errors.append(f"field '{attr.name}' must be unique")
    return errors


