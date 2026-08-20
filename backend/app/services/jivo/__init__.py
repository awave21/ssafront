"""Интеграция канала Jivo (Bot API)."""

from __future__ import annotations

from app.services.jivo.client import (
    JivoClientError,
    build_outbound_url,
    is_outbound_configured,
    send_bot_message,
)
from app.services.jivo.dedup import claim_event

__all__ = [
    "JivoClientError",
    "build_outbound_url",
    "is_outbound_configured",
    "send_bot_message",
    "claim_event",
]
