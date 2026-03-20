from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.security import AuthError, decode_token

settings = get_settings()


def rate_limit_key(request: Request) -> str:
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            ctx = decode_token(token)
            return f"{ctx.tenant_id}:{ctx.user_id}"
        except AuthError:
            pass
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key, default_limits=[settings.rate_limit_default])
