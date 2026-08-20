"""Работа с пользовательскими таблицами из правил агента.

Действия `table_find` и `table_write` живут поверх той же модели, что и таблицы
в интерфейсе («База знаний → Таблицы»), и переиспользуют её валидацию. Отличие
от роутера одно: здесь нет commit — правила исполняются внутри общей транзакции
и коммитятся вызывающим кодом.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.user_table import UserTable, UserTableAttribute, UserTableRecord
from app.services.user_table.service import (
    SYSTEM_CREATED_AT_FIELD_NAME,
    SYSTEM_ID_FIELD_NAME,
    validate_record_data,
)

logger = structlog.get_logger(__name__)

TRUTHY = {"true", "1", "да", "yes", "on"}
FALSY = {"false", "0", "нет", "no", "off", ""}


class TableActionError(Exception):
    """Ошибка, из-за которой действие с таблицей не может быть выполнено."""


async def load_table(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    table_id: Any,
) -> UserTable:
    """Загрузить таблицу вместе с колонками. Бросает TableActionError, если нет."""
    try:
        table_uuid = UUID(str(table_id))
    except (TypeError, ValueError) as exc:
        raise TableActionError("invalid_table_id") from exc

    stmt = (
        select(UserTable)
        .options(selectinload(UserTable.attributes))
        .where(
            UserTable.id == table_uuid,
            UserTable.tenant_id == tenant_id,
            UserTable.is_deleted.is_(False),
        )
    )
    table = (await db.execute(stmt)).scalars().first()
    if table is None:
        raise TableActionError("table_not_found")
    return table


def coerce_value(attr: UserTableAttribute | None, value: Any) -> Any:
    """Привести значение к типу колонки.

    Шаблоны `{{...}}` всегда отдают строку, а колонка может быть числом или
    флагом — без приведения validate_record_data отвергнет «5» для integer.
    Значение, которое привести не удалось, возвращаем как есть: пусть на нём
    ругается валидатор с понятным сообщением, а не мы молча.
    """
    if attr is None or value is None:
        return value

    kind = attr.attribute_type
    if kind == "integer":
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return value
    if kind == "float":
        try:
            return float(str(value).strip().replace(",", "."))
        except (TypeError, ValueError):
            return value
    if kind == "boolean":
        if isinstance(value, bool):
            return value
        token = str(value).strip().lower()
        if token in TRUTHY:
            return True
        if token in FALSY:
            return False
        return value
    if kind == "text_array":
        if isinstance(value, list):
            return value
        return [item.strip() for item in str(value).split(",") if item.strip()]
    return str(value)


def _attributes_by_name(table: UserTable) -> dict[str, UserTableAttribute]:
    return {attr.name: attr for attr in table.attributes}


async def find_record(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    table: UserTable,
    column: str,
    value: Any,
) -> UserTableRecord | None:
    """Найти запись по точному совпадению значения в колонке.

    Сравниваем как текст: в JSONB число могло лечь и числом, и строкой (импорт
    CSV кладёт строки), а искать пользователь будет по тому, что видит.
    """
    column = str(column or "").strip()
    if not column:
        raise TableActionError("empty_match_column")

    stmt = (
        select(UserTableRecord)
        .where(
            UserTableRecord.table_id == table.id,
            UserTableRecord.tenant_id == tenant_id,
            UserTableRecord.is_deleted.is_(False),
            UserTableRecord.data[column].astext == str(value),
        )
        .order_by(UserTableRecord.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def insert_record(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    table: UserTable,
    values: dict[str, Any],
    source: str = "agent",
) -> dict[str, Any]:
    """Добавить строку. Системные поля (id, created_at) проставляем сами."""
    attrs = _attributes_by_name(table)
    data: dict[str, Any] = {
        name: coerce_value(attrs.get(name), raw)
        for name, raw in values.items()
        if name in attrs
    }
    data[SYSTEM_ID_FIELD_NAME] = table.next_row_id
    data.setdefault(SYSTEM_CREATED_AT_FIELD_NAME, datetime.now(timezone.utc).isoformat())

    errors = await validate_record_data(db, table=table, data=data)
    if errors:
        raise TableActionError("; ".join(errors))

    table.next_row_id += 1
    table.records_count += 1
    db.add(
        UserTableRecord(
            tenant_id=tenant_id,
            table_id=table.id,
            data=data,
            source=source,
        )
    )
    await db.flush()
    return data


async def update_record(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    table: UserTable,
    record: UserTableRecord,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Обновить поля существующей строки, не трогая остальные."""
    attrs = _attributes_by_name(table)
    data = dict(record.data or {})
    for name, raw in values.items():
        if name in attrs:
            data[name] = coerce_value(attrs.get(name), raw)

    errors = await validate_record_data(
        db, table=table, data=data, ignore_record_id=record.id
    )
    if errors:
        raise TableActionError("; ".join(errors))

    # Присваиваем новый словарь целиком: SQLAlchemy не отслеживает изменения
    # внутри JSONB по месту, мутация не сохранилась бы.
    record.data = data
    await db.flush()
    return data
