from __future__ import annotations

from app.services.function_rules_runtime import _extract_session_identity


def test_extract_session_identity_parses_platform_and_user() -> None:
    assert _extract_session_identity("telegram:306597938") == ("telegram", "306597938")


def test_extract_session_identity_returns_none_for_invalid_values() -> None:
    assert _extract_session_identity("") is None
    assert _extract_session_identity("no-delimiter") is None
    assert _extract_session_identity(":123") is None
    assert _extract_session_identity("telegram:") is None
