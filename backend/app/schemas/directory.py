from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# === Вспомогательные типы ===

# Основные типы колонок (4 типа)
ColumnType = Literal[
    "text",
    "number",
    "date",
    "bool",
]

# Legacy типы для обратной совместимости
LEGACY_TYPE_MAP: dict[str, str] = {
    "varchar": "text",
    "string": "text",
    "numeric": "number",
    "integer": "number",
    "bigint": "number",
    "float": "number",
    "decimal": "number",
    "boolean": "bool",
}

DirectoryTemplate = Literal[
    "qa",
    "service_catalog",
    "product_catalog",
    "company_info",
    "custom",
]

ResponseMode = Literal["function_result", "direct_message"]

SearchType = Literal["exact", "fuzzy", "semantic"]


# Предустановленные колонки по шаблонам
TEMPLATE_COLUMNS: dict[str, list[dict[str, Any]]] = {
    "qa": [
        {"name": "question", "label": "Вопрос", "type": "text", "required": True, "searchable": True},
        {"name": "answer", "label": "Ответ", "type": "text", "required": True, "searchable": False},
    ],
    "service_catalog": [
        {"name": "name", "label": "Название", "type": "text", "required": True, "searchable": True},
        {"name": "description", "label": "Описание", "type": "text", "required": False, "searchable": True},
        {"name": "price", "label": "Цена", "type": "number", "required": False, "searchable": False},
    ],
    "product_catalog": [
        {"name": "name", "label": "Название", "type": "text", "required": True, "searchable": True},
        {"name": "description", "label": "Описание", "type": "text", "required": False, "searchable": True},
        {"name": "price", "label": "Цена", "type": "number", "required": False, "searchable": False},
        {"name": "specs", "label": "Характеристики", "type": "text", "required": False, "searchable": True},
    ],
    "company_info": [
        {"name": "topic", "label": "Тема", "type": "text", "required": True, "searchable": True},
        {"name": "info", "label": "Информация", "type": "text", "required": True, "searchable": True},
    ],
    "custom": [],
}


class ColumnDefinition(BaseModel):
    """
    Определение колонки справочника.
    
    Поддерживаемые типы:
    - text: строка любой длины
    - number: число (целое или дробное)
    - date: дата в формате YYYY-MM-DD
    - bool: true/false
    """

    name: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=100)
    type: str = Field(default="text", description="Column type: text, number, date, bool")
    required: bool = False
    searchable: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Имя колонки: латиница, цифры, _, начинается с буквы."""
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError(
                f"Invalid column name '{v}'. Must start with lowercase letter "
                "and contain only lowercase letters, digits, and underscores."
            )
        return v

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, v: str) -> str:
        """Нормализует тип колонки, конвертируя legacy типы."""
        if v in LEGACY_TYPE_MAP:
            return LEGACY_TYPE_MAP[v]
        if v not in ("text", "number", "date", "bool"):
            raise ValueError(
                f"Invalid column type '{v}'. Supported types: text, number, date, bool"
            )
        return v


# === Directory Schemas ===


def _normalize_tool_name(name: str) -> str:
    """
    Нормализует строку в валидное имя инструмента.
    
    Транслитерирует кириллицу, приводит к нижнему регистру,
    заменяет пробелы и спецсимволы на подчёркивания.
    """
    # Транслитерация кириллицы
    translit_map = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    result = name.lower()
    for cyr, lat in translit_map.items():
        result = result.replace(cyr, lat)
    
    # Заменяем всё кроме букв и цифр на подчёркивание
    result = re.sub(r"[^a-z0-9]+", "_", result)
    # Убираем начальные и конечные подчёркивания
    result = result.strip("_")
    # Убираем множественные подчёркивания
    result = re.sub(r"_+", "_", result)
    
    # Если начинается с цифры, добавляем префикс
    if result and result[0].isdigit():
        result = "dir_" + result
    
    return result or "directory"


class DirectoryBase(BaseModel):
    """Базовые поля справочника."""

    name: str = Field(min_length=1, max_length=200)
    tool_name: str | None = Field(default=None, max_length=100)
    tool_description: str | None = Field(default=None, max_length=500)
    template: DirectoryTemplate = "custom"
    columns: list[ColumnDefinition] | None = None
    response_mode: ResponseMode = "function_result"
    search_type: SearchType = "fuzzy"

    @field_validator("tool_name", mode="before")
    @classmethod
    def normalize_tool_name(cls, v: str | None) -> str | None:
        """Нормализует tool_name, если передан."""
        if v is None or v == "":
            return None
        # Нормализуем значение
        return _normalize_tool_name(v)


class DirectoryCreate(DirectoryBase):
    """Схема создания справочника."""

    @model_validator(mode="after")
    def validate_and_generate(self) -> "DirectoryCreate":
        """Валидация и автогенерация полей."""
        # Генерируем tool_name из name, если не передан
        if self.tool_name is None or self.tool_name == "":
            self.tool_name = _normalize_tool_name(self.name)
        
        # Проверяем, что tool_name валиден после нормализации
        if not re.match(r"^[a-z][a-z0-9_]*$", self.tool_name):
            # Если всё ещё невалиден, генерируем fallback
            self.tool_name = "directory"
        
        # Заполнить колонки из шаблона, если не переданы
        if self.columns is None:
            if self.template == "custom":
                raise ValueError("columns are required when template is 'custom'")
            self.columns = [ColumnDefinition(**col) for col in TEMPLATE_COLUMNS[self.template]]
        
        # Проверки
        if len(self.columns) < 1:
            raise ValueError("At least one column is required")
        if len(self.columns) > 15:
            raise ValueError("Maximum 15 columns allowed")
        
        # Уникальность имён колонок
        names = [col.name for col in self.columns]
        if len(names) != len(set(names)):
            raise ValueError("Column names must be unique")
        
        return self


class DirectoryUpdate(BaseModel):
    """Схема обновления справочника."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    tool_name: str | None = Field(default=None, max_length=100)
    tool_description: str | None = Field(default=None, max_length=500)
    columns: list[ColumnDefinition] | None = None
    response_mode: ResponseMode | None = None
    search_type: SearchType | None = None
    is_enabled: bool | None = None

    @field_validator("tool_name", mode="before")
    @classmethod
    def normalize_tool_name(cls, v: str | None) -> str | None:
        """Нормализует tool_name, если передан."""
        if v is None or v == "":
            return None
        # Нормализуем значение
        return _normalize_tool_name(v)

    @model_validator(mode="after")
    def validate_columns(self) -> "DirectoryUpdate":
        if self.columns is not None:
            if len(self.columns) < 1:
                raise ValueError("At least one column is required")
            if len(self.columns) > 15:
                raise ValueError("Maximum 15 columns allowed")
            names = [col.name for col in self.columns]
            if len(names) != len(set(names)):
                raise ValueError("Column names must be unique")
        return self


class DirectoryRead(BaseModel):
    """Схема чтения справочника."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    name: str
    slug: str
    tool_name: str
    tool_description: str | None
    template: DirectoryTemplate
    columns: list[ColumnDefinition]
    response_mode: ResponseMode
    search_type: SearchType
    is_enabled: bool
    items_count: int
    created_at: datetime
    updated_at: datetime | None = None


class DirectoryToggle(BaseModel):
    """Схема для быстрого включения/выключения справочника."""

    is_enabled: bool


# === DirectoryItem Schemas ===


class DirectoryItemBase(BaseModel):
    """Базовые поля записи справочника."""

    data: dict[str, Any]


class DirectoryItemCreate(DirectoryItemBase):
    """Схема создания записи."""

    pass


class DirectoryItemUpdate(DirectoryItemBase):
    """Схема обновления записи."""

    pass


class DirectoryItemRead(DirectoryItemBase):
    """Схема чтения записи."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    directory_id: UUID
    created_at: datetime
    updated_at: datetime | None = None


class DirectoryItemsListResponse(BaseModel):
    """Ответ с пагинацией записей справочника."""

    items: list[DirectoryItemRead]
    total: int
    limit: int
    offset: int


class DirectoryItemsBulkCreate(BaseModel):
    """Схема массового создания записей."""

    items: list[DirectoryItemCreate]
    replace_all: bool = False


class DirectoryItemsBulkCreateResponse(BaseModel):
    """Ответ на массовое создание."""

    created: int
    errors: list[dict[str, Any]] = []


class DirectoryItemsBulkDelete(BaseModel):
    """Схема массового удаления записей."""

    ids: list[UUID]


# === Search Schemas ===


class DirectorySearchRequest(BaseModel):
    """Запрос поиска по справочнику."""

    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=5, ge=1, le=20)


class DirectorySearchResultItem(BaseModel):
    """Один результат поиска."""

    id: UUID
    data: dict[str, Any]
    relevance: float = Field(ge=0, le=1)


class DirectorySearchResponse(BaseModel):
    """Ответ поиска по справочнику."""

    results: list[DirectorySearchResultItem]


class KnowledgeSearchResultItem(BaseModel):
    """Результат универсального поиска по всем справочникам."""

    directory_id: UUID
    directory_name: str
    item: DirectorySearchResultItem
    relevance: float = Field(ge=0, le=1)


class KnowledgeSearchResponse(BaseModel):
    """Ответ универсального поиска."""

    results: list[KnowledgeSearchResultItem]


# === Import/Export Schemas ===


class ImportPreviewResponse(BaseModel):
    """Ответ превью импорта."""

    columns: list[str]
    rows_count: int
    preview: list[list[Any]]
    suggested_mapping: dict[str, str | None]


class ImportRequest(BaseModel):
    """Параметры импорта."""

    mapping: dict[str, str | None]
    has_header: bool = True
    replace_all: bool = False


class ImportResponse(BaseModel):
    """Ответ импорта."""

    created: int
    skipped: int = 0
    errors: list[dict[str, Any]] = []
