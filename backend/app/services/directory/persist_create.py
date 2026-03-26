"""Транзакционное создание справочника с демо-записями."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.directory import Directory, DirectoryItem

ValidateRowFn = Callable[[dict[str, Any], list[dict[str, Any]], int], list[str]]


class DemoItemValidationFailed(Exception):
    """Ошибка валидации тела демо-строки (до commit)."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(errors)


async def persist_directory_with_demo_items(
    db: AsyncSession,
    *,
    directory: Directory,
    columns_data: list[dict[str, Any]],
    demo_rows: list[dict[str, str]],
    tenant_id: UUID,
    validate_item_row: ValidateRowFn,
) -> None:
    """
    Одна транзакция: directory (flush для id) + N демо DirectoryItem + commit.
    При любой ошибке после add(directory) — rollback (справочник не остаётся в БД).
    """
    db.add(directory)
    try:
        await db.flush()
        for row_num, row in enumerate(demo_rows, start=1):
            data = dict(row)
            errors = validate_item_row(data, columns_data, row_num)
            if errors:
                raise DemoItemValidationFailed(errors)
            db.add(
                DirectoryItem(
                    tenant_id=tenant_id,
                    directory_id=directory.id,
                    data=data,
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
