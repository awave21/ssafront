from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class LLMParams(BaseModel):
    """
    Параметры модели LLM.
    
    Поддерживаемые параметры для моделей OpenAI.
    """
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Контролирует случайность ответов. Выше = более креативно, ниже = более детерминировано."
    )
    max_tokens: int | None = Field(
        default=None,
        ge=1,
        le=100000,
        description="Максимальное количество токенов в ответе."
    )
    top_p: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Nucleus sampling. Альтернатива temperature для контроля разнообразия."
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        description="Количество токенов для рассмотрения при семплировании (для некоторых моделей)."
    )
    frequency_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Штраф за частое повторение токенов. Положительные значения уменьшают повторения."
    )
    presence_penalty: float | None = Field(
        default=None,
        ge=-2.0,
        le=2.0,
        description="Штраф за использование уже встречавшихся токенов. Стимулирует новые темы."
    )
    stop: list[str] | str | None = Field(
        default=None,
        description="Стоп-последовательности. Модель остановится при их генерации."
    )
    seed: int | None = Field(
        default=None,
        description="Seed для детерминированной генерации (если поддерживается моделью)."
    )
    
    model_config = ConfigDict(extra='allow')  # Разрешить дополнительные поля для специфичных параметров


class AgentBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    system_prompt: str = ""
    model: str = Field(
        default="openai:gpt-4.1",
        min_length=1,
        max_length=200,
        description=(
            "Модель LLM в формате 'провайдер:имя-модели'. "
            "Примеры OpenAI: openai:gpt-4.1, openai:gpt-4o-mini, openai:gpt-5.2. "
            "Примеры Anthropic: anthropic:claude-sonnet-4-5, anthropic:claude-3-5-sonnet-20241022"
        )
    )
    llm_params: LLMParams | dict[str, Any] | None = None
    status: Literal["draft", "published"] = "draft"
    version: int = 1
    max_history_messages: int = Field(default=50, ge=1, le=1000, description="Количество сообщений истории для хранения")
    max_tool_calls: int | None = Field(
        default=None,
        ge=1,
        le=50,
        description=(
            "Максимум tool-вызовов в одном запуске агента. "
            "Если не задано — используется глобальный RUNTIME_TOOL_CALLS_LIMIT. "
            "Увеличьте для сложных агентов-планировщиков, уменьшите для простых FAQ-ботов."
        ),
    )
    direct_questions_limit: int | None = Field(
        default=None,
        ge=1,
        le=500,
        description=(
            "Максимум элементов базы знаний, передаваемых в контекст агента за один запрос. "
            "Если не задано — используется глобальный DIRECT_QUESTIONS_ROUTER_MAX_ITEMS (80). "
            "Уменьшите для экономии токенов, если база знаний большая."
        ),
    )
    summary_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Инструкция для суммаризатора истории диалога. "
            "Если не задано — генерируется автоматически на основе системного промпта агента. "
            "Используйте для кастомизации формата памяти под конкретную нишу."
        ),
    )
    knowledge_tool_description: str | None = Field(
        default=None,
        max_length=4000,
        description=(
            "Кастомное описание инструмента search_knowledge_files. "
            "Если не задано — используется системное описание по умолчанию."
        ),
    )
    manager_pause_minutes: int = Field(default=10, ge=1, le=1440, description="Длительность автопаузы агента после сообщения менеджера (минуты)")
    timezone: str = Field(
        default="UTC",
        max_length=50,
        description="Часовой пояс агента в формате IANA (например, Europe/Moscow, Asia/Yekaterinburg, UTC)",
    )
    function_rules_enabled: bool = Field(default=True, description="Включены ли function-rules для агента")
    function_rules_allow_semantic: bool = Field(
        default=True, description="Разрешено ли semantic matching для function-rules агента",
    )

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        if v not in available_timezones() and v != "UTC":
            raise ValueError(f"Неизвестный часовой пояс: {v}. Используйте IANA формат, например: Europe/Moscow")
        return v

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        if v == "string":
            return "openai:gpt-4.1"
        return v

    @field_validator('llm_params', mode='before')
    @classmethod
    def validate_llm_params(cls, v: Any) -> LLMParams | dict[str, Any] | None:
        """
        Валидировать параметры LLM.
        
        Принимает dict и конвертирует в LLMParams для валидации,
        но сохраняет как dict для совместимости с JSONB.
        """
        if v is None:
            return None
        
        if isinstance(v, dict):
            # Попытаться валидировать через LLMParams
            try:
                validated = LLMParams(**v)
                # Вернуть dict для хранения в БД
                return validated.model_dump(exclude_none=True)
            except Exception as e:
                raise ValueError(f"Invalid LLM parameters: {str(e)}")
        
        return v


class AgentCreate(AgentBase):
    pass


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    llm_params: LLMParams | dict[str, Any] | None = None
    status: Literal["draft", "published"] | None = None
    version: int | None = None
    max_history_messages: int | None = Field(default=None, ge=1, le=1000)
    max_tool_calls: int | None = Field(default=None, ge=1, le=50)
    direct_questions_limit: int | None = Field(default=None, ge=1, le=500)
    summary_prompt: str | None = Field(default=None, max_length=2000)
    knowledge_tool_description: str | None = Field(default=None, max_length=4000)
    manager_pause_minutes: int | None = Field(default=None, ge=1, le=1440, description="Длительность автопаузы агента после сообщения менеджера (минуты)")
    is_disabled: bool | None = None
    sqns_enabled: bool | None = None
    sqns_configured: bool | None = None
    sqns_host: str | None = None
    sqns_credential_id: UUID | None = None
    sqns_status: str | None = None
    sqns_last_sync_at: datetime | None = None
    sqns_last_activity_at: datetime | None = None
    sqns_error: str | None = None
    sqns_disabled_tools: list[str] | None = None
    sqns_tool_descriptions: dict[str, str] | None = None
    timezone: str | None = Field(
        default=None,
        max_length=50,
        description="Часовой пояс агента в формате IANA (например, Europe/Moscow, Asia/Yekaterinburg, UTC)",
    )
    function_rules_enabled: bool | None = None
    function_rules_allow_semantic: bool | None = None
    runtime_bridges_mode: Literal["auto", "manual"] | None = Field(
        default=None,
        description=(
            '"auto" — скрытые вставки: bridge-инструкции, снимок state, стиль эксперта, '
            "дата/время, блок SQNS. "
            '"manual" (по умолчанию) — в LLM уходит только system_prompt из UI, '
            "без перечисленного; инструкции и факты — в шаблоне промпта и в ответах тулов."
        ),
    )

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None and v not in available_timezones() and v != "UTC":
            raise ValueError(f"Неизвестный часовой пояс: {v}. Используйте IANA формат, например: Europe/Moscow")
        return v

    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        if v == "string":
            return "openai:gpt-4.1"
        return v

    @field_validator('llm_params', mode='before')
    @classmethod
    def validate_llm_params(cls, v: Any) -> LLMParams | dict[str, Any] | None:
        """Валидировать параметры LLM."""
        if v is None:
            return None
        
        if isinstance(v, dict):
            try:
                validated = LLMParams(**v)
                return validated.model_dump(exclude_none=True)
            except Exception as e:
                raise ValueError(f"Invalid LLM parameters: {str(e)}")
        
        return v


class AgentRead(AgentBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    owner_user_id: UUID
    created_at: datetime
    updated_at: datetime | None = None
    is_disabled: bool = False
    sqns_enabled: bool = False
    sqns_configured: bool = False
    sqns_host: str | None = None
    sqns_credential_id: UUID | None = None
    sqns_status: str | None = None
    sqns_last_sync_at: datetime | None = None
    sqns_last_activity_at: datetime | None = None
    sqns_error: str | None = None
    sqns_warning: str | None = None
    sqns_disabled_tools: list[str] = Field(default_factory=list)
    sqns_tool_descriptions: dict[str, str] = Field(default_factory=dict)
    max_tool_calls: int | None = None
    direct_questions_limit: int | None = None
    summary_prompt: str | None = None
    knowledge_tool_description: str | None = None
    runtime_bridges_mode: str = Field(default="manual")
    total_cost_usd: Decimal = Field(default=Decimal("0"), description="Суммарные расходы агента в USD")
    total_cost_rub: Decimal = Field(default=Decimal("0"), description="Суммарные расходы агента в RUB")


class SqnsTool(BaseModel):
    name: str
    description: str
    is_enabled: bool = Field(default=True, alias="isEnabled")
    required_fields: list[str] = Field(default_factory=list, alias="requiredFields")
    data_sources: dict[str, str] = Field(default_factory=dict, alias="dataSources")


class SqnsStatus(BaseModel):
    sqns_enabled: bool = Field(alias="sqnsEnabled")
    sqns_host: str | None = Field(None, alias="sqnsHost")
    sqns_last_sync_at: datetime | None = Field(None, alias="sqnsLastSyncAt")
    sqns_last_activity_at: datetime | None = Field(None, alias="sqnsLastActivityAt")
    sqns_status: str | None = Field(None, alias="sqnsStatus")
    sqns_error: str | None = Field(None, alias="sqnsError")
    sqns_tools: list[SqnsTool] = Field(default_factory=list, alias="sqnsTools")


def get_sqns_tools_definitions() -> list[dict[str, Any]]:
    """
    Legacy tool definitions для SQNS (используется когда FastMCP недоступен).
    
    Для полной документации см. docs/sqns-tools-reference.md
    """
    from app.services.sqns.tool_texts import get_sqns_tool_description

    return [
        {
            "name": "sqns_find_booking_options",
            "method": "find_booking_options",
            "description": get_sqns_tool_description("sqns_find_booking_options"),
            "schema": {
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Название услуги для нечеткого поиска (например: 'чистка', 'консультация').",
                    },
                    "specialist_name": {
                        "type": "string",
                        "description": "Имя/ФИО специалиста для нечеткого поиска (например: 'Иванов').",
                    },
                    "category": {
                        "type": "string",
                        "description": (
                            "Необязательно: фильтр по категории услуги (нечёткий ILIKE). "
                            "Точные названия категорий — инструмент sqns_list_categories."
                        ),
                    },
                },
                "required": [],
            },
        },
        {
            "name": "sqns_list_resources",
            "method": "list_resources",
            "description": get_sqns_tool_description("sqns_list_resources"),
            "schema": {
                "type": "object",
                "properties": {},
                "required": []
            },
        },
        {
            "name": "sqns_list_services",
            "method": "list_services",
            "description": get_sqns_tool_description("sqns_list_services"),
            "schema": {
                "type": "object",
                "properties": {},
                "required": []
            },
        },
        {
            "name": "sqns_list_categories",
            "method": "list_service_categories",
            "description": get_sqns_tool_description("sqns_list_categories"),
            "schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "sqns_find_client",
            "method": "find_client_by_phone",
            "description": get_sqns_tool_description("sqns_find_client"),
            "schema": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": (
                            "Телефон клиента в любом формате (с кодом страны или без, с пробелами/дефисами). "
                            "Примеры: +79001234567, 8-900-123-45-67, 9001234567."
                        ),
                    }
                },
                "required": ["phone"],
            },
        },
        {
            "name": "sqns_list_slots",
            "method": "list_slots",
            "description": get_sqns_tool_description("sqns_list_slots"),
            "schema": {
                "type": "object",
                "properties": {
                    "resource_id": {
                        "type": "integer",
                        "description": "external_id специалиста из sqns_find_booking_options или sqns_list_resources. Обязательный параметр.",
                    },
                    "date": {
                        "type": "string",
                        "format": "date",
                        "description": "Дата в формате YYYY-MM-DD (например, 2026-01-29). Обязательный параметр.",
                    },
                    "service_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": (
                            "МАССИВ external_id услуг из sqns_find_booking_options или sqns_list_services. "
                            "Даже для одной услуги передавай массив: [1], а не просто 1. Обязательный параметр."
                        ),
                    },
                },
                "required": ["resource_id", "date", "service_ids"],
            },
        },
        {
            "name": "sqns_list_visits",
            "method": "list_visits",
            "description": get_sqns_tool_description("sqns_list_visits"),
            "schema": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": "Телефон клиента. Обязательно: список визитов должен быть только по конкретному клиенту.",
                    },
                    "date_from": {
                        "type": "string",
                        "format": "date",
                        "description": "Начальная дата периода в формате YYYY-MM-DD (например, 2026-01-25). Обязательный параметр.",
                    },
                    "date_till": {
                        "type": "string",
                        "format": "date",
                        "description": "Конечная дата периода в формате YYYY-MM-DD (например, 2026-01-31). Обязательный параметр.",
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Количество записей на страницу (по умолчанию 100, максимум 100).",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["phone", "date_from", "date_till"],
            },
        },
        {
            "name": "sqns_client_visits",
            "method": "list_visits",
            "description": get_sqns_tool_description("sqns_client_visits"),
            "schema": {
                "type": "object",
                "properties": {
                    "phone": {
                        "type": "string",
                        "description": (
                            "Телефон клиента. Обязателен. "
                            "Все найденные визиты должны принадлежать только этому клиенту."
                        ),
                    },
                    "date": {
                        "type": "string",
                        "format": "date",
                        "description": (
                            "Одна дата в формате YYYY-MM-DD для поиска на конкретный день. "
                            "Передай либо это поле, либо пару date_from + date_till (не оба варианта)."
                        ),
                    },
                    "date_from": {
                        "type": "string",
                        "format": "date",
                        "description": (
                            "Начало диапазона YYYY-MM-DD. "
                            "Используй вместе с date_till; альтернатива одному полю date."
                        ),
                    },
                    "date_till": {
                        "type": "string",
                        "format": "date",
                        "description": (
                            "Конец диапазона YYYY-MM-DD. "
                            "Используй вместе с date_from; альтернатива одному полю date."
                        ),
                    },
                    "per_page": {
                        "type": "integer",
                        "description": "Количество записей на страницу (по умолчанию 100, максимум 100).",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["phone"],
            },
        },
        {
            "name": "sqns_create_visit",
            "method": "create_visit",
            "description": get_sqns_tool_description("sqns_create_visit"),
            "schema": {
                "type": "object",
                "properties": {
                    "resource_id": {
                        "type": "integer",
                        "description": "ID специалиста из sqns_list_resources. Обязательный параметр.",
                    },
                    "service_id": {
                        "type": "integer",
                        "description": "ID услуги из sqns_list_services. Обязательный параметр.",
                    },
                    "datetime": {
                        "type": "string",
                        "format": "date-time",
                        "description": (
                            "Дата и время приема в формате ISO 8601 (например, 2026-01-25T14:00:00+05:00). "
                            "Только из свободных слотов (sqns_list_slots). Обязательный параметр."
                        ),
                    },
                    "user_name": {
                        "type": "string",
                        "description": (
                            "ФИО клиента: из sqns_find_client (client.name) или от пользователя. Обязателен."
                        ),
                    },
                    "phone": {
                        "type": "string",
                        "description": (
                            "Телефон клиента: из sqns_find_client (client.phone) или от пользователя. Обязателен."
                        ),
                    },
                    "email": {
                        "type": "string",
                        "description": "Email клиента. Необязателен, можно не передавать.",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Комментарий к записи (например, 'Первичный прием'). Опционально.",
                    },
                },
                "required": ["resource_id", "service_id", "datetime", "user_name", "phone"],
            },
        },
        {
            "name": "sqns_update_visit",
            "method": "update_visit",
            "description": get_sqns_tool_description("sqns_update_visit"),
            "schema": {
                "type": "object",
                "properties": {
                    "visit_id": {
                        "type": "integer",
                        "description": (
                            "ID записи для обновления. "
                            "Получи из sqns_list_visits или из результата sqns_create_visit. Обязательный параметр."
                        ),
                    },
                    "datetime": {
                        "type": "string",
                        "format": "date-time",
                        "description": (
                            "Новая дата и время приема в формате ISO 8601 (например, 2026-01-26T10:00:00). "
                            "Используй, если клиент хочет перенести запись. Проверь свободные слоты через sqns_list_slots."
                        ),
                    },
                    "comment": {
                        "type": "string",
                        "description": "Новый или дополнительный комментарий к записи.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["confirmed", "cancelled", "completed", "no_show"],
                        "description": "Новый статус визита (confirmed, cancelled, completed, no_show).",
                    },
                },
                "required": ["visit_id"],
            },
        },
        {
            "name": "sqns_delete_visit",
            "method": "delete_visit",
            "description": get_sqns_tool_description("sqns_delete_visit"),
            "schema": {
                "type": "object",
                "properties": {
                    "visit_id": {
                        "type": "integer",
                        "description": (
                            "ID записи для удаления. "
                            "Получи из sqns_list_visits или из результата sqns_create_visit. Обязательный параметр."
                        ),
                    },
                },
                "required": ["visit_id"],
            },
        },
    ]
