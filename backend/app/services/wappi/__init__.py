"""Интеграция с WAPPI API."""

from app.services.wappi.client import (
    WappiAuthQrResult,
    WappiBalanceAddDaysResult,
    WappiClient,
    WappiClientError,
    WappiPlatform,
    WappiProfileCreateResult,
    WappiProfileDeleteResult,
)
from app.services.wappi.binding import (
    ChannelProfileAlreadyBoundError,
    ChannelProfileBindingError,
    ChannelProfileConfigError,
    ChannelProfileExternalError,
    ChannelProfileNotBoundError,
    ChannelProfileUnsupportedTypeError,
    bind_profile_to_channel,
    build_wappi_client,
    request_channel_auth_qr,
    unbind_profile_from_channel,
)

__all__ = [
    "WappiClient",
    "WappiClientError",
    "WappiPlatform",
    "WappiAuthQrResult",
    "WappiBalanceAddDaysResult",
    "WappiProfileCreateResult",
    "WappiProfileDeleteResult",
    "ChannelProfileAlreadyBoundError",
    "ChannelProfileBindingError",
    "ChannelProfileConfigError",
    "ChannelProfileExternalError",
    "ChannelProfileNotBoundError",
    "ChannelProfileUnsupportedTypeError",
    "bind_profile_to_channel",
    "build_wappi_client",
    "request_channel_auth_qr",
    "unbind_profile_from_channel",
]
