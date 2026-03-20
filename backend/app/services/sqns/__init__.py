"""
SQNS package — интеграция с SQNS CRM.

Re-exports для обратной совместимости:
    from app.services.sqns import SQNSClient, SQNSClientError
"""

from app.services.sqns.client import (
    SQNSClient,
    SQNSClientError,
    fetch_token_by_login,
)

__all__ = [
    "SQNSClient",
    "SQNSClientError",
    "fetch_token_by_login",
]
