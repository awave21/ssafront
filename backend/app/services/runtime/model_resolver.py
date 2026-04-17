"""Resolve pydantic-ai model with optional per-tenant API keys.

When a tenant has configured a custom key, we create a provider-bound model
(OpenAIChatModel, AnthropicModel, or legacy OpenAIModel).

Supports pydantic-ai >=0.7 (OpenAIChatModel + OpenAIProvider, AnthropicModel +
AnthropicProvider) and older 0.0.x releases (OpenAIModel + openai_client).
"""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def provider_prefix_from_model_name(model_name: str) -> str | None:
    """Return the provider prefix before ``:``, lowercased, or None."""
    name = (model_name or "").strip()
    if not name or ":" not in name:
        return None
    return name.split(":", 1)[0].strip().lower() or None


def resolve_model(
    model_name: str,
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> Any:
    """Return a pydantic-ai-compatible model identifier.

    Parameters
    ----------
    model_name:
        Model string in pydantic-ai format, e.g. ``"openai:gpt-4o"``,
        ``"anthropic:claude-sonnet-4-5"``.
    openai_api_key:
        If provided and *model_name* starts with ``openai:``, an OpenAI chat
        model with this key is returned.
    anthropic_api_key:
        If provided and *model_name* starts with ``anthropic:``, an Anthropic
        model with this key is returned.

    If the matching key is missing, *model_name* is returned unchanged (env
    variables may apply at runtime).
    """
    if not model_name or not str(model_name).strip():
        return model_name

    model_name = str(model_name).strip()

    if model_name.startswith("anthropic:"):
        if not anthropic_api_key:
            return model_name
        bare_model = model_name.split(":", 1)[1]
        try:
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider

            provider = AnthropicProvider(api_key=anthropic_api_key)
            logger.info(
                "using_tenant_anthropic_key",
                model=bare_model,
                api="AnthropicProvider",
            )
            return AnthropicModel(bare_model, provider=provider)
        except ImportError:
            logger.warning("pydantic_ai_anthropic_model_import_failed_falling_back")
            return model_name

    if not model_name.startswith("openai:"):
        if openai_api_key or anthropic_api_key:
            logger.warning(
                "custom_key_ignored_unsupported_model_prefix",
                model_name=model_name,
            )
        return model_name

    if not openai_api_key:
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
        import openai as openai_lib
        from pydantic_ai.models.openai import OpenAIModel

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
