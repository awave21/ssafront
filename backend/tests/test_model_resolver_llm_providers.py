from __future__ import annotations

import pytest

from app.services.runtime.model_resolver import (
    provider_prefix_from_model_name,
    resolve_model,
)


def test_provider_prefix_from_model_name() -> None:
    assert provider_prefix_from_model_name("anthropic:claude-sonnet-4-5") == "anthropic"
    assert provider_prefix_from_model_name("openai:gpt-4.1") == "openai"
    assert provider_prefix_from_model_name("") is None
    assert provider_prefix_from_model_name("nocolon") is None


def test_resolve_model_without_keys_returns_raw_string() -> None:
    assert resolve_model("openai:gpt-4.1", openai_api_key=None) == "openai:gpt-4.1"
    assert resolve_model("anthropic:claude-3-5-haiku-20241022", anthropic_api_key=None) == (
        "anthropic:claude-3-5-haiku-20241022"
    )


def test_resolve_model_openai_uses_key_when_available() -> None:
    try:
        from pydantic_ai.models.openai import OpenAIChatModel
    except ImportError:
        pytest.skip("pydantic-ai openai model not available")
    m = resolve_model(
        "openai:gpt-4.1-mini",
        openai_api_key="sk-proj-test123456789012345678901234567890",
    )
    assert isinstance(m, OpenAIChatModel)


def test_resolve_model_anthropic_uses_key_when_available() -> None:
    try:
        from pydantic_ai.models.anthropic import AnthropicModel
    except ImportError:
        pytest.skip("pydantic-ai anthropic model not available")
    m = resolve_model(
        "anthropic:claude-3-5-haiku-20241022",
        anthropic_api_key="sk-ant-api03-testkeyfortests0123456789012",
    )
    assert isinstance(m, AnthropicModel)
