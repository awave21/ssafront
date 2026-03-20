"""Integration API schemas for public chat endpoint."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request schema for /integrations/chat"""
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: Optional[str] = Field(default=None, max_length=200)


class ChatResponse(BaseModel):
    """Response schema for /integrations/chat"""
    response: str
    session_id: str
    run_id: UUID


class ChatMessage(BaseModel):
    """Single message in chat history"""
    role: str
    content: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    """Response schema for /integrations/chat/history"""
    messages: list[ChatMessage]
