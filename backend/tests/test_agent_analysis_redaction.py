from app.services.agent_analysis.redaction import redact_any, redact_text


def test_redact_text_masks_common_sensitive_patterns() -> None:
    src = (
        "email user@example.com phone +1 (555) 111-22-33 "
        "card 4111 1111 1111 1111 token sk-testsecretvalue12345"
    )
    out = redact_text(src)
    assert "user@example.com" not in out
    assert "+1 (555) 111-22-33" not in out
    assert "4111 1111 1111 1111" not in out
    assert "sk-testsecretvalue12345" not in out
    assert "[REDACTED_EMAIL]" in out
    assert "[REDACTED_PHONE]" in out
    assert "[REDACTED_CARD]" in out
    assert "[REDACTED_TOKEN]" in out


def test_redact_any_masks_secret_keys_recursively() -> None:
    payload = {
        "authorization": "Bearer abc",
        "nested": {
            "api_key": "xyz",
            "text": "contact me at owner@corp.local",
        },
    }
    out = redact_any(payload)
    assert out["authorization"] == "[REDACTED_SECRET]"
    assert out["nested"]["api_key"] == "[REDACTED_SECRET]"
    assert out["nested"]["text"] != payload["nested"]["text"]
    assert "[REDACTED_EMAIL]" in out["nested"]["text"]
