from __future__ import annotations

import logging
import structlog
import logfire
import time

from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import OperationalError, DisconnectionError

from app.api.routers import api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import bind_trace_id, configure_logging

logger = structlog.get_logger()

# Настройка Logfire для мониторинга (PydanticAI + HTTPX)
# Требуется переменная окружения LOGFIRE_TOKEN или авторизация через logfire auth
try:
    logfire.configure(metrics=logfire.MetricsOptions(collect_in_spans=True))
    logfire.instrument_pydantic_ai()
    logfire.instrument_httpx(capture_all=True)
    logger.info("logfire_configured")
except Exception as e:
    logger.warning("logfire_configuration_failed", error=str(e))


def _build_error_payload(
    *,
    error: str,
    message: str,
    detail: str | dict | list | None = None,
    field_errors: dict[str, list[str]] | None = None,
    extra: dict | None = None,
) -> dict:
    payload: dict = {
        "error": error,
        "message": message,
        "detail": detail,
        "field_errors": field_errors,
    }
    if extra:
        payload.update(extra)
    return payload


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("app_starting")
    configure_logging()
    logger.info("app_started_successfully")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    if not settings.cors_origins:
        raise ValueError("CORS_ORIGINS must contain at least one explicit origin for cookie auth")
    if settings.auth_refresh_cookie_samesite == "none" and not settings.auth_refresh_cookie_secure:
        raise ValueError("AUTH_REFRESH_COOKIE_SAMESITE='none' requires AUTH_REFRESH_COOKIE_SECURE=true")

    app.state.limiter = limiter
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_exception_handler(OperationalError, _database_error_handler)
    app.add_exception_handler(DisconnectionError, _database_error_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(SlowAPIMiddleware)

    @app.middleware("http")
    async def access_logging_middleware(request: Request, call_next):
        start_time = time.time()
        client_host = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        try:
            response = await call_next(request)
            process_time = time.time() - start_time
            
            logger.info(
                "api_request",
                method=request.method,
                path=request.url.path,
                client_ip=client_host,
                user_agent=user_agent,
                status_code=response.status_code,
                duration=process_time
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "api_request_failed",
                method=request.method,
                path=request.url.path,
                client_ip=client_host,
                user_agent=user_agent,
                error=str(e),
                duration=process_time
            )
            raise

    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):
        trace_id = request.headers.get("x-trace-id") or str(uuid4())
        bind_trace_id(trace_id)

        try:
            response = await call_next(request)
            response.headers["x-trace-id"] = trace_id
            return response
        except Exception as e:
            logger.error("middleware_error", path=str(request.url.path), error=str(e), error_type=type(e).__name__)
            raise

    app.include_router(api_router, prefix=settings.api_prefix)
    return app


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic со стандартизированным форматом."""
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        field_path = ".".join(str(loc) for loc in error.get("loc", []))
        error_msg = error.get("msg", "Validation error")
        if field_path not in field_errors:
            field_errors[field_path] = []
        field_errors[field_path].append(error_msg)

    content = _build_error_payload(
        error="validation_error",
        message="Validation failed",
        detail="Validation failed",
        field_errors=field_errors,
    )
    return JSONResponse(status_code=422, content=content)


async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Обработчик ошибок rate limiting с стандартизированным форматом."""
    # Определяем время ожидания в зависимости от эндпоинта
    retry_after = 60  # по умолчанию 1 минута
    if request.url.path.endswith("/register"):
        retry_after = 3600  # 1 час для регистрации
        message = f"Превышен лимит попыток регистрации. Пожалуйста, попробуйте снова через {retry_after // 60} минут."
    elif request.url.path.endswith("/login"):
        retry_after = 60  # 1 минута для входа
        message = f"Превышен лимит попыток входа. Пожалуйста, попробуйте снова через {retry_after} секунд."
    elif request.url.path.endswith("/refresh"):
        retry_after = 60  # 1 минута для обновления токена
        message = f"Превышен лимит попыток обновления токена. Пожалуйста, попробуйте снова через {retry_after} секунд."
    else:
        message = f"Превышен лимит запросов. Пожалуйста, попробуйте снова через {retry_after} секунд."
    
    content = _build_error_payload(
        error="rate_limit_exceeded",
        message=message,
        detail=message,
        field_errors=None,
        extra={"retry_after": retry_after},
    )
    response = JSONResponse(status_code=429, content=content)
    response.headers["Retry-After"] = str(retry_after)
    return response


async def _database_error_handler(request: Request, exc: OperationalError | DisconnectionError) -> JSONResponse:
    """Обработчик ошибок подключения к базе данных."""
    logger.error(
        "database_connection_error path=%s method=%s: %s",
        request.url.path,
        request.method,
        exc,
        exc_info=True,
    )
    error_msg = str(exc)
    
    # Определяем тип ошибки для более понятного сообщения
    if "password authentication failed" in error_msg.lower():
        detail = "Database authentication failed. Check DATABASE_URL configuration."
    elif "connection" in error_msg.lower() and ("refused" in error_msg.lower() or "closed" in error_msg.lower()):
        detail = "Database connection failed. The database may be unavailable or the connection pool is exhausted."
    elif "does not exist" in error_msg.lower() or "relation" in error_msg.lower():
        detail = "Database schema error. Migrations may not be applied. Run: alembic upgrade head"
    else:
        detail = f"Database error: {error_msg}"
    
    content = _build_error_payload(
        error="database_error",
        message="Database operation failed",
        detail=detail,
        field_errors=None,
    )
    try:
        if get_settings().environment == "dev":
            content["hint"] = "Check: docker compose logs api --tail 100 && docker compose logs db --tail 100"
            content["original_error"] = error_msg
    except Exception:  # noqa: S110
        pass
    
    return JSONResponse(status_code=503, content=content)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        headers = exc.headers or None
        normalized = _build_error_payload(
            error="http_error",
            message="HTTP error",
            detail=exc.detail if not isinstance(exc.detail, dict) else None,
            field_errors=None,
        )
        if isinstance(exc.detail, dict):
            normalized["error"] = str(exc.detail.get("error", f"http_{exc.status_code}"))
            normalized["message"] = str(exc.detail.get("message", "HTTP error"))
            normalized["detail"] = exc.detail.get("detail")
            normalized["field_errors"] = exc.detail.get("field_errors")
            for key, value in exc.detail.items():
                if key not in {"error", "message", "detail", "field_errors"}:
                    normalized[key] = value
        else:
            normalized["error"] = f"http_{exc.status_code}"
            normalized["message"] = str(exc.detail)
            normalized["detail"] = str(exc.detail)
        return JSONResponse(status_code=exc.status_code, content=normalized, headers=headers)
    logger.exception(
        "unhandled_exception path=%s method=%s: %s",
        request.url.path,
        request.method,
        exc,
    )
    content = _build_error_payload(
        error="internal_server_error",
        message="Internal Server Error",
        detail="Internal Server Error",
        field_errors=None,
    )
    try:
        if get_settings().environment == "dev":
            content["hint"] = "Run: docker compose logs api --tail 100"
    except Exception:  # noqa: S110
        pass
    return JSONResponse(status_code=500, content=content)


app = create_app()
