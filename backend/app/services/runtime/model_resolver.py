"""Resolve pydantic-ai model with optional per-tenant OpenAI API key.

When a tenant has configured a custom key, we create an OpenAIChatModel
(or the legacy OpenAIModel) with an explicit provider / client.

Supports both pydantic-ai >=0.7 (OpenAIChatModel + OpenAIProvider)
and older 0.0.x releases (OpenAIModel + openai_client kwarg).
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def resolve_model(model_name: str, *, openai_api_key: str | None = None) -> Any:
    """Return a pydantic-ai-compatible model identifier.

    Parameters
    ----------
    model_name:
        Model string in pydantic-ai format, e.g. ``"openai:gpt-4o"``.
    openai_api_key:
        If provided, an ``OpenAIChatModel`` (or legacy ``OpenAIModel``)
        with a tenant-specific API key is returned.  Otherwise the raw
        *model_name* string is returned unchanged.
    """
    if not openai_api_key:
        return model_name

    if not model_name.startswith("openai:"):
        logger.warning(
            "custom_key_ignored_non_openai_model",
            model_name=model_name,
        )
        return model_name

    bare_model = model_name.split(":", 1)[1]

    # --- New API (pydantic-ai >=0.7): OpenAIChatModel + OpenAIProvider ---
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(api_key=openai_api_key)
        logger.info("using_tenant_openai_key", model=bare_model, api="OpenAIProvider")
        return OpenAIChatModel(bare_model, provider=provider)
    except ImportError:
        pass

    # --- Legacy API (pydantic-ai 0.0.x): OpenAIModel + openai_client ---
    try:
        from pydantic_ai.models.openai import OpenAIModel
        import openai as openai_lib

        client = openai_lib.AsyncOpenAI(api_key=openai_api_key)
        logger.info("using_tenant_openai_key", model=bare_model, api="OpenAIModel_legacy")
        return OpenAIModel(bare_model, openai_client=client)
    except ImportError:
        pass

    logger.warning("pydantic_ai_openai_model_import_failed_falling_back")
    return model_name


def resolve_openai_client(*, openai_api_key: str | None = None) -> Any:
    """Return an ``openai.AsyncOpenAI`` client with an explicit API key.

    Used for direct OpenAI SDK calls (e.g. embeddings). Global env fallback
    is intentionally disabled: caller must provide a tenant key.
    """
    import openai as openai_lib

    if not openai_api_key:
        raise ValueError("OpenAI API key is required")
    return openai_lib.AsyncOpenAI(api_key=openai_api_key)
