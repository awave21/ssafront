from __future__ import annotations

from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class UserTable(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_tables"

    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    next_row_id: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)

    attributes: Mapped[list["UserTableAttribute"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
        order_by="UserTableAttribute.order_index",
    )
    records: Mapped[list["UserTableRecord"]] = relationship(
        back_populates="table",
        cascade="all, delete-orphan",
    )


class UserTableAttribute(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_table_attributes"
    __table_args__ = (
        UniqueConstraint("table_id", "name", name="uq_user_table_attribute_name"),
    )

    table_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    attribute_type: Mapped[str] = mapped_column(String(50), nullable=False)
    type_config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    is_searchable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    default_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)

    table: Mapped["UserTable"] = relationship(back_populates="attributes")


class UserTableRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user_table_records"

    table_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("user_tables.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), index=True, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="admin", server_default="admin", nullable=False)

    table: Mapped["UserTable"] = relationship(back_populates="records")
