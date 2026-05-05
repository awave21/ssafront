from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Telegram Bot Token format: 123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_TOKEN_PATTERN = re.compile(r"^\d{8,15}:[A-Za-z0-9_-]{30,50}$")
COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


class WidgetSettings(BaseModel):
    title: str = Field(default="Чат с нами", max_length=60)
    subtitle: str | None = Field(None, max_length=100)
    welcome_message: str | None = Field(None, max_length=500)
    primary_color: str = Field(default="#3B82F6", pattern=r"^#[0-9a-fA-F]{6}$")
    position: Literal["bottom-right", "bottom-left"] = Field(default="bottom-right")
    launcher_icon: Literal["chat", "bubble", "sparkle"] = Field(default="chat")

    model_config = ConfigDict(extra="forbid")


class ChannelBase(BaseModel):
    type: Literal["telegram", "telegram_phone", "whatsapp", "max", "web_widget"] = Field(..., description="Тип канала")
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
    type: Literal["telegram", "telegram_phone", "whatsapp", "max", "web_widget"] | None = Field(None, description="Тип канала")
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


PublicChannelType = Literal["Telegram_Bot", "Telegram_Phone", "Whatsapp_Phone", "Max_Phone", "Web_Widget"]


class ChannelConnectionPayload(BaseModel):
    type: PublicChannelType = Field(..., description="Тип канала")
    telegram_bot_token: str | None = Field(None, max_length=100, description="Токен Telegram-бота")
    whatsapp_phone: str | None = Field(None, description="Телефон WhatsApp")
    max_bot_id: str | None = Field(None, max_length=64, description="ID бота Wappi MAX (query bot_id при отправке)")
    widget_settings: WidgetSettings | None = Field(None, description="Настройки виджета")
    widget_allowed_origins: list[str] | None = Field(None, description="Разрешённые домены (пусто = все)")

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
        if self.type != "Max_Phone" and self.max_bot_id:
            raise ValueError("max_bot_id is only allowed for Max_Phone")
        return self


class ChannelDisconnectPayload(BaseModel):
    type: PublicChannelType = Field(..., description="Тип канала")

    model_config = ConfigDict(extra="forbid")


class ChannelRead(ChannelBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_authorized: bool = Field(default=False, validation_alias="phone_is_authorized")
    wappi_profile_id: str | None = None
    wappi_max_bot_id: str | None = None
    created_at: datetime
    updated_at: datetime | None

    # Web widget fields
    widget_settings: WidgetSettings | None = None
    widget_allowed_origins: list[str] | None = None
    widget_api_key_last4: str | None = None


class ChannelConnectRead(ChannelRead):
    """Returned only on connect — includes one-time raw API key."""
    raw_api_key: str | None = None


class ChannelAuthQrRead(BaseModel):
    status: str
    qr_code: str | None = Field(None, description="QR код в формате data URL")
    requires_2fa: bool = Field(False, description="Требуется ввод 2FA пароля")
    detail: str | None = Field(None, description="Дополнительная информация от сервиса авторизации")
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None


class ChannelAuth2FAPayload(BaseModel):
    pwd_code: str = Field(..., min_length=1, max_length=256, description="Пароль двухфакторной авторизации")

    model_config = ConfigDict(extra="forbid")

    @field_validator("pwd_code")
    @classmethod
    def validate_pwd_code(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("pwd_code must not be empty")
        return normalized


class ChannelAuth2FARead(BaseModel):
    status: str
    detail: str | None = None
    uuid: str | None = None
    time: str | None = None
    timestamp: int | None = None


class WidgetRotateKeyRead(BaseModel):
    raw_api_key: str
    last4: str
