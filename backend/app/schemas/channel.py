from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Telegram Bot Token format: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_TOKEN_PATTERN = re.compile(r"^\d{8,15}:[A-Za-z0-9_-]{30,50}$")


class ChannelBase(BaseModel):
    type: Literal["telegram", "telegram_phone", "whatsapp", "max"] = Field(..., description="Тип канала")
    telegram_bot_token: str | None = Field(None, description="Токен Telegram-бота")
    telegram_webhook_enabled: bool = Field(False, description="Активен ли webhook")
    telegram_webhook_endpoint: str | None = Field(None, description="Webhook endpoint для Telegram")


class ChannelCreate(ChannelBase):
    @model_validator(mode="after")
    def validate_create(self) -> "ChannelCreate":
        if self.type == "telegram" and not self.telegram_bot_token:
            raise ValueError("telegram_bot_token is required for telegram")
        if self.type != "telegram":
            if self.telegram_bot_token or self.telegram_webhook_enabled or self.telegram_webhook_endpoint:
                raise ValueError("telegram fields are only allowed for telegram")
        return self


class ChannelUpdate(BaseModel):
    type: Literal["telegram", "telegram_phone", "whatsapp", "max"] | None = Field(None, description="Тип канала")
    telegram_bot_token: str | None = Field(None, description="Токен Telegram-бота")
    telegram_webhook_enabled: bool | None = Field(None, description="Активен ли webhook")
    telegram_webhook_endpoint: str | None = Field(None, description="Webhook endpoint для Telegram")

    model_config = ConfigDict(extra="forbid")


class TelegramBotTokenUpdate(BaseModel):
    telegram_bot_token: str = Field(..., min_length=1, max_length=100, description="Токен Telegram-бота")

    model_config = ConfigDict(extra="forbid")

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_telegram_token_format(cls, v: str) -> str:
        if not TELEGRAM_TOKEN_PATTERN.match(v):
            raise ValueError(
                "Invalid Telegram bot token format. "
                "Expected format: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
            )
        return v


PublicChannelType = Literal["Telegram_Bot", "Telegram_Phone", "Whatsapp_Phone", "Max_Phone"]


class ChannelConnectionPayload(BaseModel):
    type: PublicChannelType = Field(..., description="Тип канала")
    telegram_bot_token: str | None = Field(None, max_length=100, description="Токен Telegram-бота")
    whatsapp_phone: str | None = Field(None, description="Телефон WhatsApp")

    model_config = ConfigDict(extra="forbid")

    @field_validator("telegram_bot_token")
    @classmethod
    def validate_telegram_token_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not TELEGRAM_TOKEN_PATTERN.match(v):
            raise ValueError(
                "Invalid Telegram bot token format. "
                "Expected format: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
            )
        return v

    @model_validator(mode="after")
    def validate_payload(self) -> "ChannelConnectionPayload":
        if self.type == "Telegram_Bot":
            if not self.telegram_bot_token:
                raise ValueError("telegram_bot_token is required for Telegram_Bot")
        if self.type != "Telegram_Bot" and self.telegram_bot_token:
            raise ValueError("telegram_bot_token is only allowed for Telegram_Bot")
        if self.type != "Whatsapp_Phone" and self.whatsapp_phone:
            raise ValueError("whatsapp_phone is only allowed for Whatsapp_Phone")
        return self


class ChannelDisconnectPayload(BaseModel):
    type: PublicChannelType = Field(..., description="Тип канала")

    model_config = ConfigDict(extra="forbid")


class ChannelRead(ChannelBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_authorized: bool = Field(default=False, validation_alias="phone_is_authorized")
    created_at: datetime
    updated_at: datetime | None


class ChannelAuthQrRead(BaseModel):
    status: str
    qr_code: str = Field(..., description="QR код в формате data URL")
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None
