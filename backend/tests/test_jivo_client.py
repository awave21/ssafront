from app.services.jivo.client import build_outbound_url


def test_build_outbound_url_adds_provider_id_and_token_to_base_url() -> None:
    assert build_outbound_url(
        "https://bot.jivosite.com/webhooks",
        "MKBRrqKKf6xM0Jo",
        "provider-token",
    ) == "https://bot.jivosite.com/webhooks/MKBRrqKKf6xM0Jo/provider-token"


def test_build_outbound_url_preserves_complete_url_from_jivo() -> None:
    assert build_outbound_url(
        "https://bot.jivosite.com/webhooks/MKBRrqKKf6xM0Jo/provider-token",
        "MKBRrqKKf6xM0Jo",
        "provider-token",
    ) == "https://bot.jivosite.com/webhooks/MKBRrqKKf6xM0Jo/provider-token"
