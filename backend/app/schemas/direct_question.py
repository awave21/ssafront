from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DirectQuestionFilePayload(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1, max_length=255)
    url: str = Field(min_length=1, max_length=5000)
    size: int | None = Field(default=None, ge=0)
    type: str | None = Field(default=None, max_length=100)


class DirectQuestionFollowup(BaseModel):
    enabled: bool = False
    content: str = ""
    delay_minutes: int = 60

    @model_validator(mode="after")
    def validate_followup(self) -> "DirectQuestionFollowup":
        if self.enabled:
            if not self.content.strip():
                raise ValueError("followup.content is required when followup.enabled=true")
            if not (1 <= self.delay_minutes <= 10080):
                raise ValueError("followup.delay_minutes must be between 1 and 10080")
        return self


class DirectQuestionBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    is_enabled: bool = True
    interrupt_dialog: bool = False
    notify_telegram: bool = False
    files: list[DirectQuestionFilePayload] = Field(default_factory=list)
    followup: DirectQuestionFollowup | None = None

    @field_validator("title", "content")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        if len(tags) > 20:
            raise ValueError("maximum 20 tags allowed")
        normalized: list[str] = []
        for tag in tags:
            clean = tag.strip()
            if not clean:
                continue
            if len(clean) > 50:
                raise ValueError("tag length must be <= 50")
            normalized.append(clean)
        return normalized

    @field_validator("files")
    @classmethod
    def validate_files_limit(cls, files: list[DirectQuestionFilePayload]) -> list[DirectQuestionFilePayload]:
        if len(files) > 20:
            raise ValueError("maximum 20 files allowed")
        return files


class DirectQuestionCreate(DirectQuestionBase):
    pass


class DirectQuestionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    is_enabled: bool | None = None
    interrupt_dialog: bool | None = None
    notify_telegram: bool | None = None
    files: list[DirectQuestionFilePayload] | None = None
    followup: DirectQuestionFollowup | None = None

    @field_validator("title", "content")
    @classmethod
    def validate_optional_non_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def validate_optional_tags(cls, tags: list[str] | None) -> list[str] | None:
        if tags is None:
            return None
        if len(tags) > 20:
            raise ValueError("maximum 20 tags allowed")
        normalized: list[str] = []
        for tag in tags:
            clean = tag.strip()
            if not clean:
                continue
            if len(clean) > 50:
                raise ValueError("tag length must be <= 50")
            normalized.append(clean)
        return normalized

    @field_validator("files")
    @classmethod
    def validate_optional_files_limit(cls, files: list[DirectQuestionFilePayload] | None) -> list[DirectQuestionFilePayload] | None:
        if files is not None and len(files) > 20:
            raise ValueError("maximum 20 files allowed")
        return files


class DirectQuestionFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    size: int | None = None
    type: str | None = None
    sort_order: int
    created_at: datetime


class DirectQuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    agent_id: UUID
    title: str
    content: str
    tags: list[str]
    is_enabled: bool
    interrupt_dialog: bool
    notify_telegram: bool
    followup: DirectQuestionFollowup | None = None
    files: list[DirectQuestionFileRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class DirectQuestionToggle(BaseModel):
    is_enabled: bool


