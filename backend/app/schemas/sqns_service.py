from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# Resource (Specialist) Schemas
# ============================================================================


class SqnsResourceBase(BaseModel):
    """Базовая схема для специалиста SQNS."""

    name: str = Field(..., description="ФИО специалиста")
    specialization: str | None = Field(None, description="Специализация (например: Стоматолог)")
    is_active: bool = Field(True, description="Активен ли специалист")
    active: bool = Field(True, description="Включен ли специалист для использования агентом")
    information: str | None = Field(None, description="Дополнительное описание специалиста")


class SqnsResourceRead(SqnsResourceBase):
    """Схема для чтения специалиста из БД."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    external_id: int = Field(..., description="ID специалиста в SQNS")
    raw_data: dict[str, Any] | None = Field(None, description="Полные данные из SQNS API")
    synced_at: datetime = Field(..., description="Время последней синхронизации")
    created_at: datetime
    updated_at: datetime | None


class SqnsResourceListItem(BaseModel):
    """Краткая информация о специалисте для списков."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: int
    name: str
    specialization: str | None
    is_active: bool
    active: bool
    information: str | None


class SqnsSpecialistListItem(BaseModel):
    """Данные специалиста для вкладки управления SQNS."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: int
    name: str
    role: str | None = None
    email: str | None = None
    phone: str | None = None
    services_count: int = 0
    linked_services: int = 0
    is_active: bool
    active: bool
    information: str | None = None


class SqnsSpecialistUpdate(BaseModel):
    """Обновление полей специалиста для конкретного агента."""

    model_config = ConfigDict(extra="forbid")

    active: bool | None = Field(None, description="Включить/отключить специалиста для агента")
    information: str | None = Field(None, description="Описание/примечание по специалисту")


# ============================================================================
# Service Schemas
# ============================================================================


class SqnsServiceBase(BaseModel):
    """Базовая схема для услуги SQNS."""

    name: str = Field(..., description="Название услуги")
    category: str | None = Field(None, description="Категория услуги")
    price: Decimal | None = Field(None, description="Цена услуги", ge=0)
    duration_seconds: int = Field(..., description="Длительность в секундах", ge=0)
    description: str | None = Field(None, description="Описание услуги")


class SqnsServiceRead(SqnsServiceBase):
    """Схема для чтения услуги из БД."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    external_id: int = Field(..., description="ID услуги в SQNS")
    is_enabled: bool = Field(..., description="Включена ли услуга для агента")
    priority: int = Field(..., description="Приоритет (выше = важнее)")
    raw_data: dict[str, Any] | None = Field(None, description="Полные данные из SQNS API")
    synced_at: datetime = Field(..., description="Время последней синхронизации")
    created_at: datetime
    updated_at: datetime | None


class SqnsServiceListItem(BaseModel):
    """Краткая информация об услуге для списков."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: int
    name: str
    category: str | None
    price: Decimal | None
    duration_seconds: int
    is_enabled: bool
    priority: int
    # Количество специалистов, которые могут выполнять эту услугу
    specialists_count: int | None = Field(None, description="Количество специалистов для этой услуги")
    price_range: str | None = Field(None, description="Диапазон цен (если есть)")


class SqnsServiceUpdate(BaseModel):
    """Схема для обновления услуги."""

    is_enabled: bool | None = Field(None, description="Включить/отключить услугу")
    priority: int | None = Field(None, description="Изменить приоритет", ge=0)


class SqnsServiceBulkUpdate(BaseModel):
    """Схема для массового обновления услуг."""

    service_ids: list[UUID] = Field(..., description="Список ID услуг для обновления")
    is_enabled: bool | None = Field(None, description="Включить/отключить услуги")
    priority: int | None = Field(None, description="Установить приоритет", ge=0)


# ============================================================================
# Category Schemas
# ============================================================================


class SqnsCategoryBase(BaseModel):
    """Базовая схема для категории услуг."""

    name: str = Field(..., description="Название категории")
    is_enabled: bool = Field(True, description="Включена ли категория")
    priority: int = Field(0, description="Приоритет (выше = важнее)", ge=0)


class SqnsCategoryRead(SqnsCategoryBase):
    """Схема для чтения категории из БД."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    created_at: datetime
    updated_at: datetime | None
    # Количество услуг в категории
    services_count: int | None = Field(None, description="Количество услуг в категории")


class SqnsCategoryUpdate(BaseModel):
    """Схема для обновления категории."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    is_enabled: bool | None = Field(None, alias="isEnabled", description="Включить/отключить категорию")
    priority: int | None = Field(None, description="Изменить приоритет", ge=0)


# ============================================================================
# Sync Result Schema
# ============================================================================


class SyncResult(BaseModel):
    """Результат синхронизации данных из SQNS."""

    success: bool = Field(..., description="Успешна ли синхронизация")
    message: str = Field(..., description="Описание результата")
    resources_synced: int = Field(0, description="Количество синхронизированных специалистов")
    services_synced: int = Field(0, description="Количество синхронизированных услуг")
    categories_synced: int = Field(0, description="Количество синхронизированных категорий")
    links_synced: int = Field(0, description="Количество связей услуга-специалист")
    employees_synced: int = Field(0, description="Количество синхронизированных сотрудников")
    clients_synced: int = Field(0, description="Количество синхронизированных клиентов")
    commodities_synced: int = Field(0, description="Количество синхронизированных товаров")
    visits_synced: int = Field(0, description="Количество синхронизированных визитов")
    payments_synced: int = Field(0, description="Количество синхронизированных платежей")
    synced_at: datetime | None = Field(None, description="Время синхронизации")
    errors: list[str] = Field(default_factory=list, description="Список ошибок, если были")


# ============================================================================
# Search and Filter Schemas
# ============================================================================


class ServiceSearchParams(BaseModel):
    """Параметры поиска услуг."""

    search: str | None = Field(None, description="Поиск по названию/описанию (ILIKE)")
    category: str | None = Field(None, description="Фильтр по категории")
    is_enabled: bool | None = Field(None, description="Фильтр по статусу (включена/отключена)")
    resource_id: UUID | None = Field(None, description="Фильтр по специалисту (UUID из БД)")
    limit: int = Field(20, description="Максимум результатов", ge=1, le=100)
    offset: int = Field(0, description="Смещение для пагинации", ge=0)


# ============================================================================
# MCP Tool Schemas (for sqns_find_booking_options)
# ============================================================================


class BookingOptionsInput(BaseModel):
    """
    Входные параметры для инструмента sqns_find_booking_options.
    
    Агент может передать:
    - Только service_name → найти специалистов для услуги
    - Только specialist_name → найти услуги специалиста
    - Оба параметра → проверить совместимость и вернуть ID для записи
    - Ничего → топ услуг по priority (см. лимит выдачи в реализации)
    """

    service_name: str | None = Field(
        None,
        description="Название услуги для поиска (ILIKE поиск по содержанию, например: 'чистка' найдет 'Профессиональная чистка зубов')",
    )
    specialist_name: str | None = Field(
        None,
        description="ФИО специалиста для поиска (ILIKE поиск по содержанию, например: 'Иванов' найдет 'Иванов Иван Иванович')",
    )


class BookingAlternative(BaseModel):
    """Альтернативный вариант (другой специалист или услуга)."""

    id: int = Field(
        ..., 
        description=(
            "external_id для SQNS API (используй это поле для sqns_list_slots). "
            "КРИТИЧЕСКИ ВАЖНО: Это external_id (число), НЕ внутренний UUID!"
        )
    )
    name: str = Field(..., description="Название услуги или ФИО специалиста")
    additional_info: str | None = Field(None, description="Дополнительная информация")


class BookingOptionsOutput(BaseModel):
    """
    Выходные данные инструмента sqns_find_booking_options.
    
    ready=True означает, что можно сразу вызывать sqns_list_slots
    с указанными service_id и resource_id.
    """

    ready: bool = Field(
        ...,
        description=(
            "Готово ли для вызова sqns_list_slots (совместимость проверена). "
            "Если ready=True, используй service_id и resource_id из КОРНЯ ответа. "
            "Если ready=False, используй id из выбранного элемента в alternatives."
        ),
    )
    service_id: int | None = Field(
        None,
        description=(
            "external_id услуги для SQNS API (используется в sqns_list_slots). "
            "КРИТИЧЕСКИ ВАЖНО: Используй ЭТО поле только если ready=True. "
            "Если ready=False, используй поле 'id' из выбранного элемента в alternatives."
        ),
    )
    service_name: str | None = Field(None, description="Название найденной услуги")
    resource_id: int | None = Field(
        None,
        description=(
            "external_id специалиста для SQNS API (используется в sqns_list_slots). "
            "КРИТИЧЕСКИ ВАЖНО: Используй ЭТО поле только если ready=True. "
            "Если ready=False, используй поле 'id' из выбранного элемента в alternatives."
        ),
    )
    resource_name: str | None = Field(None, description="ФИО найденного специалиста")
    message: str = Field(..., description="Описание статуса или инструкции для агента")
    alternatives: dict[str, list[BookingAlternative]] = Field(
        default_factory=dict,
        description=(
            "Альтернативные варианты: {'services': [...], 'specialists': [...], "
            "'compatible_pairs': [...] при нескольких совместимых парах услуга+специалист (см. additional_info с обоими id), "
            "'other_specialists': [...], 'other_services': [...]}. "
            "Если ready=False, используй поле 'id' из выбранного элемента (это external_id услуги или специалиста для SQNS API), "
            "а для compatible_pairs читай оба id в additional_info."
        ),
    )
    # Дополнительная информация для агента
    duration_seconds: int | None = Field(None, description="Длительность услуги в секундах")
    price: str | None = Field(None, description="Цена услуги (отформатированная строка)")


# ============================================================================
# Service-Resource Link Schema
# ============================================================================


class SqnsServiceResourceRead(BaseModel):
    """Связь между услугой и специалистом."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    resource_id: UUID
    duration_seconds: int | None = Field(None, description="Override длительности для специалиста")
    created_at: datetime
    updated_at: datetime | None


# ============================================================================
# Client list (Patients page)
# ============================================================================


class SqnsClientListItem(BaseModel):
    """Клиент SQNS для страницы «Пациенты»."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: int
    name: str | None = None
    phone: str | None = None
    birth_date: str | None = None
    sex: int | None = None
    client_type: str | None = None
    visits_count: int | None = None
    total_arrival: Decimal | None = None
    tags: list[str] | None = None
    last_visit_datetime: datetime | None = None
    last_service_name: str | None = None
    last_specialist_name: str | None = None
    last_visit_total_price: Decimal | None = Field(
        default=None,
        description="Сумма приёма (total_price) для визита в колонке «Визит».",
    )
    slice_revenue: Decimal | None = Field(
        default=None,
        description=(
            "Выручка клиента за срез vf/vt/vc (сумма total_cost/total_price по его визитам периода). "
            "None — срез не задан, используется total_arrival."
        ),
    )
    slice_visits_count: int | None = Field(
        default=None,
        description=(
            "Число визитов клиента в срезе vf/vt/vc (с учётом vc-фильтра). "
            "None — срез не задан, используется visits_count (всё время)."
        ),
    )
    synced_at: datetime


class SqnsClientsListResponse(BaseModel):
    clients: list[SqnsClientListItem]
    total: int
    limit: int
    offset: int
    has_more: bool
    revenue_total: Decimal = Field(
        default=Decimal("0"),
        description=(
            "Выручка по текущей выборке (все страницы): при срезе vf/vt/vc — сумма "
            "total_cost/total_price по визитам периода, попавшим в когорту; иначе — сумма total_arrival по клиентам."
        ),
    )
    total_arrival_sum: Decimal = Field(
        default=Decimal("0"),
        description="Сумма total_arrival по клиентам выборки (итого по колонке «Всего» в таблице).",
    )
    visits_count_sum: int = Field(
        default=0,
        description="Сумма поля visits_count по всем клиентам выборки (для строки «Итого» в таблице).",
    )
    last_visit_total_price_sum: Decimal = Field(
        default=Decimal("0"),
        description=(
            "Сумма total_price «визита в строке» (ближайший будущий или последний прошедший состоявшийся) "
            "по всем клиентам выборки."
        ),
    )
    slice_visit_count: int | None = Field(
        default=None,
        description=(
            "Число визитов в срезе vf/vt/vc с учётом tz, channel и tags (как KPI «Записи»/«Дошедшие» в аналитике). "
            "None, если срез по визитам не задан."
        ),
    )
    top_service_name: str | None = Field(
        default=None,
        description="Услуга с наибольшим числом визитов в кэше среди клиентов текущей выборки (после поиска).",
    )
    top_service_bookings: int | None = Field(
        default=None,
        description="Число визитов с этой услугой в выборке.",
    )


class SqnsClientCachedVisitItem(BaseModel):
    """Визит из кэша sqns_visits для карточки пациента."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    visit_external_id: int
    visit_datetime: datetime | None = Field(
        default=None,
        description="Дата и время приёма для сортировки/логики (парсинг поля datetime).",
    )
    visit_datetime_raw: str | None = Field(
        default=None,
        description="Строка datetime из SQNS как в ответе API — для отображения без пересчёта часового пояса.",
    )
    service_name: str | None = None
    specialist_name: str | None = None
    attendance: int | None = None
    arrived: bool = Field(
        default=False,
        description="Визит считается состоявшимся (явка/завершён): attendance>0 или статус в raw_data.",
    )
    total_price: Decimal | None = None


class SqnsClientCachedVisitsResponse(BaseModel):
    visits: list[SqnsClientCachedVisitItem]
