from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.db.models.agent import Agent


class SqnsResource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш специалистов (врачей) из SQNS для быстрого поиска по имени.
    
    Синхронизируется с SQNS API при включении интеграции и по кнопке "Обновить".
    Удаляется CASCADE при отключении SQNS интеграции или удалении агента.
    """
    __tablename__ = "sqns_resources"

    # Связь с агентом (CASCADE delete)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Внешний ID из SQNS API
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # ФИО специалиста (с индексом для ILIKE поиска)
    name: Mapped[str] = mapped_column(String(300), nullable=False)

    # Специализация (например: "Стоматолог", "Терапевт")
    specialization: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Активен ли специалист
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Включен ли специалист для конкретного агента (ручной флаг)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Дополнительная информация/описание специалиста
    information: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Полные данные из SQNS API
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Время последней синхронизации
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    service_links: Mapped[list["SqnsServiceResource"]] = relationship(
        "SqnsServiceResource",
        back_populates="resource",
        cascade="all, delete-orphan",
    )

    # Уникальность: один external_id на агента
    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_resources_agent_external"),
    )


class SqnsService(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш услуг из SQNS для быстрого поиска и фильтрации.
    
    Frontend может включать/отключать услуги (is_enabled) и устанавливать приоритет.
    Удаляется CASCADE при отключении SQNS интеграции или удалении агента.
    """
    __tablename__ = "sqns_services"

    # Связь с агентом (CASCADE delete)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Внешний ID из SQNS API
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Название услуги (с индексом для ILIKE поиска)
    name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Категория услуги
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)

    # Цена услуги
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Длительность в секундах
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Описание услуги (с индексом для ILIKE поиска)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Включена ли услуга для агента (контроль с frontend)
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    # Приоритет для сортировки (чем выше - тем важнее)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Полные данные из SQNS API
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Время последней синхронизации
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    resource_links: Mapped[list["SqnsServiceResource"]] = relationship(
        "SqnsServiceResource",
        back_populates="service",
        cascade="all, delete-orphan",
    )

    # Уникальность: один external_id на агента
    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_services_agent_external"),
    )


class SqnsServiceResource(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Many-to-many связь между услугами и специалистами.
    
    Определяет, какой специалист может выполнять какую услугу,
    с возможностью override длительности для конкретного специалиста.
    """
    __tablename__ = "sqns_service_resources"

    # Связь с услугой (CASCADE delete)
    service_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sqns_services.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Связь со специалистом (CASCADE delete)
    resource_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("sqns_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Override длительности для конкретного специалиста (если отличается от базовой)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    service: Mapped["SqnsService"] = relationship(
        "SqnsService",
        back_populates="resource_links",
    )

    resource: Mapped["SqnsResource"] = relationship(
        "SqnsResource",
        back_populates="service_links",
    )

    # Уникальность: одна связь service-resource
    __table_args__ = (
        UniqueConstraint("service_id", "resource_id", name="uq_sqns_service_resources"),
    )


class SqnsServiceCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Настройки категорий услуг для агента.
    
    Frontend может включать/отключать целые категории и устанавливать приоритет.
    Удаляется CASCADE при отключении SQNS интеграции или удалении агента.
    """
    __tablename__ = "sqns_service_categories"

    # Связь с агентом (CASCADE delete)
    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Название категории
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Включена ли категория для агента
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Приоритет для сортировки (чем выше - тем важнее)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    # Уникальность: одна категория на агента
    __table_args__ = (
        UniqueConstraint("agent_id", "name", name="uq_sqns_categories_agent_name"),
    )


class SqnsCommodity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш товаров из SQNS.

    Используется для аналитики и фоновой синхронизации.
    """

    __tablename__ = "sqns_commodities"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    article: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_commodities_agent_external"),
    )


class SqnsEmployee(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш сотрудников из SQNS.

    Отдельно хранится от sqns_resources для аналитики и трассировки синхронизации.
    """

    __tablename__ = "sqns_employees"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    firstname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lastname: Mapped[str | None] = mapped_column(String(120), nullable=True)
    patronymic: Mapped[str | None] = mapped_column(String(120), nullable=True)
    full_name: Mapped[str] = mapped_column(String(400), nullable=False, index=True)
    image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    position: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    rating: Mapped[str | None] = mapped_column(String(50), nullable=True)
    updated_at_external: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_fired: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_employees_agent_external"),
    )


class SqnsVisit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш визитов из SQNS.
    """

    __tablename__ = "sqns_visits"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    resource_external_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    client_external_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    visit_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    attendance: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_visits_agent_external"),
    )


class SqnsPayment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш платежей из SQNS.

    SQNS не всегда отдает единый id платежа, поэтому external_id хранит детерминированный ключ.
    """

    __tablename__ = "sqns_payments"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    payment_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payment_type_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_type_handle: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_type_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    organization_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    client_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    visit_external_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_payments_agent_external"),
    )


class SqnsClientRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Кэш клиентов из SQNS.

    PII-поля хранятся в зашифрованном виде в pii_data.
    """

    __tablename__ = "sqns_clients"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sex: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_type: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    visits_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_arrival: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    pii_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "external_id", name="uq_sqns_clients_agent_external"),
    )


class SqnsSyncCursor(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Состояние курсоров синхронизации по сущностям SQNS.
    """

    __tablename__ = "sqns_sync_cursor"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    modificate_value: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    date_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_till: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("agent_id", "entity", name="uq_sqns_sync_cursor_agent_entity"),
    )


class SqnsSyncRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """
    Лог запусков синхронизации SQNS.
    """

    __tablename__ = "sqns_sync_runs"

    agent_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger: Mapped[str] = mapped_column(String(30), nullable=False, default="hourly", index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running", index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entities: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent: Mapped["Agent"] = relationship(
        "Agent",
        foreign_keys=[agent_id],
        viewonly=True,
    )
