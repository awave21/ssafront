from __future__ import annotations

from functools import lru_cache
import json
from typing import Annotated, Any, Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "agent-platform"
    environment: Literal["dev", "staging", "prod"] = "dev"
    api_prefix: str = Field(default="/api/v1", validation_alias="API_PREFIX")
    public_base_url: str = Field(default="http://localhost:8000", validation_alias="PUBLIC_BASE_URL")
    invite_link_base_url: str | None = Field(
        default=None,
        validation_alias="INVITE_LINK_BASE_URL",
        description="Base URL for invite links (frontend). Defaults to public_base_url.",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@db:5432/agents",
        validation_alias="DATABASE_URL",
    )
    redis_url: str | None = Field(
        default="redis://redis:6379/0",
        validation_alias="REDIS_URL",
    )
    db_pool_size: int = Field(default=20, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=30, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(
        default=30,
        validation_alias="DB_POOL_TIMEOUT_SECONDS",
    )
    db_pool_recycle_seconds: int = Field(
        default=1800,
        validation_alias="DB_POOL_RECYCLE_SECONDS",
    )

    jwt_secret: str = Field(default="change-me", validation_alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    jwt_audience: str = Field(default="agent-platform", validation_alias="JWT_AUDIENCE")
    jwt_issuer: str = Field(default="agent-platform", validation_alias="JWT_ISSUER")
    jwt_access_token_expires_in: str = Field(default="15m", validation_alias="JWT_ACCESS_TOKEN_EXPIRES_IN")
    jwt_refresh_token_expires_in: str = Field(default="7d", validation_alias="JWT_REFRESH_TOKEN_EXPIRES_IN")
    api_key_pepper: str = Field(default="change-me", validation_alias="API_KEY_PEPPER")
    allow_test_tokens: bool = Field(default=False, validation_alias="ALLOW_TEST_TOKENS")
    credentials_encryption_key: str | None = Field(
        default=None,
        validation_alias="CREDENTIALS_ENCRYPTION_KEY",
    )
    auth_api_keys: dict[str, dict[str, Any]] = Field(
        default_factory=dict,
        validation_alias="AUTH_API_KEYS",
    )
    auth_refresh_cookie_name: str = Field(
        default="refresh_token",
        validation_alias="AUTH_REFRESH_COOKIE_NAME",
    )
    auth_refresh_cookie_domain: str | None = Field(
        default=None,
        validation_alias="AUTH_REFRESH_COOKIE_DOMAIN",
    )
    auth_refresh_cookie_path: str = Field(
        default="/",
        validation_alias="AUTH_REFRESH_COOKIE_PATH",
    )
    auth_refresh_cookie_samesite: Literal["lax", "strict", "none"] = Field(
        default="lax",
        validation_alias="AUTH_REFRESH_COOKIE_SAMESITE",
    )
    auth_refresh_cookie_secure: bool = Field(
        default=True,
        validation_alias="AUTH_REFRESH_COOKIE_SECURE",
    )

    rate_limit_default: str = Field(default="100/minute", validation_alias="RATE_LIMIT_DEFAULT")
    rate_limit_runs: str = Field(default="20/minute", validation_alias="RATE_LIMIT_RUNS")
    rate_limit_integrations: str = Field(default="60/minute", validation_alias="RATE_LIMIT_INTEGRATIONS")
    rate_limit_auth_login: str = Field(default="15/minute", validation_alias="RATE_LIMIT_AUTH_LOGIN")
    rate_limit_auth_refresh: str = Field(default="30/minute", validation_alias="RATE_LIMIT_AUTH_REFRESH")
    rate_limit_auth_register: str = Field(
        default="3/hour", 
        validation_alias="RATE_LIMIT_AUTH_REGISTER",
        description="Лимит попыток регистрации. В dev окружении можно увеличить до 10/hour"
    )
    auth_login_bruteforce_enabled: bool = Field(
        default=True,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_ENABLED",
    )
    auth_login_bruteforce_window_seconds: int = Field(
        default=900,
        ge=60,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_WINDOW_SECONDS",
    )
    auth_login_bruteforce_progressive_enabled: bool = Field(
        default=True,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_PROGRESSIVE_ENABLED",
    )
    auth_login_bruteforce_base_block_seconds: int = Field(
        default=60,
        ge=1,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_BASE_BLOCK_SECONDS",
    )
    auth_login_bruteforce_max_block_seconds: int = Field(
        default=7200,
        ge=60,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_MAX_BLOCK_SECONDS",
    )
    auth_login_bruteforce_max_attempts_per_ip: int = Field(
        default=40,
        ge=1,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_IP",
    )
    auth_login_bruteforce_max_attempts_per_email: int = Field(
        default=10,
        ge=1,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_EMAIL",
    )
    auth_login_bruteforce_max_attempts_per_ip_email: int = Field(
        default=5,
        ge=1,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_IP_EMAIL",
    )
    auth_login_bruteforce_subnet_enabled: bool = Field(
        default=False,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_SUBNET_ENABLED",
    )
    auth_login_bruteforce_max_attempts_per_subnet: int = Field(
        default=120,
        ge=1,
        validation_alias="AUTH_LOGIN_BRUTEFORCE_MAX_ATTEMPTS_PER_SUBNET",
    )

    pydanticai_default_model: str = Field(
        default="openai:gpt-4.1-mini",
        validation_alias="PYDANTICAI_DEFAULT_MODEL",
        description=(
            "Модель по умолчанию для агентов. "
            "Поддерживаются модели OpenAI: openai:gpt-4.1, openai:gpt-4.1-mini, "
            "openai:gpt-4.1-nano, openai:gpt-4o, openai:gpt-4o-mini, openai:gpt-5.2"
        ),
    )
    summary_model: str = Field(
        default="openai:gpt-4o-mini",
        validation_alias="SUMMARY_MODEL",
        description=(
            "Модель для суммаризации старых сообщений диалога. "
            "Должна быть дешёвой — используется при каждом превышении max_history_messages."
        ),
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        validation_alias="EMBEDDING_MODEL",
        description=(
            "Модель для генерации эмбеддингов (direct questions, directory). "
            "Размерность вектора должна соответствовать схеме БД (1536 для text-embedding-3-small)."
        ),
    )
    runtime_tool_calls_limit: int = Field(
        default=5,
        ge=1,
        validation_alias="RUNTIME_TOOL_CALLS_LIMIT",
        description="Максимум успешных tool-вызовов в одном запуске агента.",
    )
    runtime_request_limit: int = Field(
        default=6,
        ge=1,
        validation_alias="RUNTIME_REQUEST_LIMIT",
        description="Максимум LLM-запросов в одном запуске агента (защита от циклов).",
    )
    runtime_strip_tool_messages_from_history: bool = Field(
        default=False,
        validation_alias="RUNTIME_STRIP_TOOL_MESSAGES_FROM_HISTORY",
        description="Удалять tool-call/tool-return из history перед запуском модели (можно включить для строгой совместимости).",
    )
    runtime_optional_tools_mode: str = Field(
        default="eager",
        validation_alias="RUNTIME_OPTIONAL_TOOLS_MODE",
        description=(
            "Режим подбора optional data-тулов: eager — всегда все категории; "
            "lazy_keywords — эвристика по тексту сообщения."
        ),
    )
    direct_questions_retrieval_router_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "DIRECT_QUESTIONS_RETRIEVAL_ROUTER_ENABLED",
            "DIRECT_QUESTIONS_ROUTER_ENABLED",
        ),
        description=(
            "Подключать data-тулы search_direct_questions и get_direct_answer (как справочники — обычные инструменты агента)."
        ),
    )
    direct_questions_max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias="DIRECT_QUESTIONS_MAX_RESULTS",
    )
    direct_questions_min_match_percent: int = Field(
        default=45,
        ge=0,
        le=100,
        validation_alias="DIRECT_QUESTIONS_MIN_MATCH_PERCENT",
    )
    direct_questions_rerank_enabled: bool = Field(
        default=True,
        validation_alias="DIRECT_QUESTIONS_RERANK_ENABLED",
        description="Гибридный rerank (вектор + лексика) для прямых вопросов.",
    )

    # Rerank для справочников: гибридный (вектор + лексика)
    directory_rerank_enabled: bool = Field(
        default=True,
        validation_alias="DIRECTORY_RERANK_ENABLED",
        description="Включить лёгкий гибридный rerank для семантического поиска в справочниках.",
    )
    directory_rerank_candidates_multiplier: int = Field(
        default=4,
        ge=2,
        le=10,
        validation_alias="DIRECTORY_RERANK_CANDIDATES_MULTIPLIER",
        description="Множитель top-N для первичной выборки перед rerank (напр., limit=5 → выбираем 20).",
    )
    directory_rerank_vector_weight: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        validation_alias="DIRECTORY_RERANK_VECTOR_WEIGHT",
        description="Вес векторного score в финальной оценке; (1-вес) идёт на лексический score.",
    )

    direct_questions_embedding_timeout_ms: int = Field(
        default=3000,
        ge=10,
        le=10000,
        validation_alias="DIRECT_QUESTIONS_EMBEDDING_TIMEOUT_MS",
    )
    direct_questions_retry_interval_seconds: int = Field(
        default=300,
        ge=30,
        validation_alias="DIRECT_QUESTIONS_RETRY_INTERVAL_SECONDS",
    )
    direct_questions_retry_batch_size: int = Field(
        default=100,
        ge=1,
        le=1000,
        validation_alias="DIRECT_QUESTIONS_RETRY_BATCH_SIZE",
    )
    direct_questions_followup_dispatch_interval_seconds: int = Field(
        default=15,
        ge=1,
        validation_alias="DIRECT_QUESTIONS_FOLLOWUP_DISPATCH_INTERVAL_SECONDS",
    )
    direct_questions_followup_dispatch_batch_size: int = Field(
        default=50,
        ge=1,
        le=1000,
        validation_alias="DIRECT_QUESTIONS_FOLLOWUP_DISPATCH_BATCH_SIZE",
    )
    direct_questions_followup_max_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias="DIRECT_QUESTIONS_FOLLOWUP_MAX_ATTEMPTS",
    )
    analysis_reports_ttl_days: int = Field(
        default=30,
        ge=1,
        validation_alias="ANALYSIS_REPORTS_TTL_DAYS",
        description="Срок хранения отчетов и рекомендаций аналитики в днях.",
    )
    analysis_analyzer_version: str = Field(
        default="agent-analysis-v1",
        validation_alias="ANALYSIS_ANALYZER_VERSION",
        description="Версия логики аналитика для трассируемости отчетов.",
    )

    logfire_reconcile_enabled: bool = Field(
        default=True,
        validation_alias="LOGFIRE_RECONCILE_ENABLED",
    )
    logfire_read_token: str | None = Field(
        default=None,
        validation_alias="LOGFIRE_READ_TOKEN",
    )
    logfire_base_url: str = Field(
        default="https://logfire-us.pydantic.dev",
        validation_alias="LOGFIRE_BASE_URL",
    )
    logfire_reconcile_initial_delay_seconds: float = Field(
        default=1.5,
        validation_alias="LOGFIRE_RECONCILE_INITIAL_DELAY_SECONDS",
    )
    logfire_reconcile_max_attempts: int = Field(
        default=3,
        validation_alias="LOGFIRE_RECONCILE_MAX_ATTEMPTS",
    )
    logfire_reconcile_retry_delay_seconds: float = Field(
        default=2.0,
        validation_alias="LOGFIRE_RECONCILE_RETRY_DELAY_SECONDS",
    )
    logfire_reconcile_timeout_seconds: int = Field(
        default=10,
        validation_alias="LOGFIRE_RECONCILE_TIMEOUT_SECONDS",
    )

    tool_default_timeout_ms: int = Field(default=15000, validation_alias="TOOL_DEFAULT_TIMEOUT_MS")
    tool_max_timeout_ms: int = Field(default=60000, validation_alias="TOOL_MAX_TIMEOUT_MS")
    tool_retry_attempts: int = Field(default=2, validation_alias="TOOL_RETRY_ATTEMPTS")
    function_rules_max_per_phase: int = Field(default=25, validation_alias="FUNCTION_RULES_MAX_PER_PHASE")
    function_rule_max_actions: int = Field(default=10, validation_alias="FUNCTION_RULE_MAX_ACTIONS")
    function_rule_webhook_timeout_seconds: float = Field(
        default=10.0, validation_alias="FUNCTION_RULE_WEBHOOK_TIMEOUT_SECONDS",
    )
    function_rules_hitl_enabled: bool = Field(default=False, validation_alias="FUNCTION_RULES_HITL_ENABLED")

    wappi_base_url: str = Field(default="https://wappi.pro", validation_alias="WAPPI_BASE_URL")
    wappi_api_token: str | None = Field(default=None, validation_alias="WAPPI_API_TOKEN")
    wappi_timeout_seconds: float = Field(default=15.0, ge=1, validation_alias="WAPPI_TIMEOUT_SECONDS")
    wappi_retry_attempts: int = Field(default=2, ge=0, validation_alias="WAPPI_RETRY_ATTEMPTS")
    wappi_retry_min_seconds: float = Field(default=0.5, ge=0, validation_alias="WAPPI_RETRY_MIN_SECONDS")
    wappi_retry_max_seconds: float = Field(default=4.0, ge=0, validation_alias="WAPPI_RETRY_MAX_SECONDS")
    wappi_async_timeout_from_seconds: int | None = Field(
        default=None,
        ge=0,
        validation_alias="WAPPI_ASYNC_TIMEOUT_FROM_SECONDS",
    )
    wappi_async_timeout_to_seconds: int | None = Field(
        default=None,
        ge=0,
        validation_alias="WAPPI_ASYNC_TIMEOUT_TO_SECONDS",
    )
    wappi_profile_tariff_id: int = Field(default=1, ge=1, le=4, validation_alias="WAPPI_PROFILE_TARIFF_ID")
    wappi_profile_promo_code: str | None = Field(default=None, validation_alias="WAPPI_PROFILE_PROMO_CODE")
    wappi_max_default_bot_id: str | None = Field(
        default=None,
        validation_alias="WAPPI_MAX_DEFAULT_BOT_ID",
        description="Fallback bot_id для MAX API, если у канала не задан wappi_max_bot_id",
    )
    alerts_telegram_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALERTS_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
    )
    alerts_telegram_chat_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ALERTS_TELEGRAM_CHAT_ID", "DEFAULT_RECIPIENT_TELEGRAM"),
    )

    sse_keepalive_seconds: int = Field(default=15, validation_alias="SSE_KEEPALIVE_SECONDS")

    sqns_sync_interval_seconds: int = Field(
        default=3600,
        ge=60,
        validation_alias="SQNS_SYNC_INTERVAL_SECONDS",
    )
    sqns_sync_batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        validation_alias="SQNS_SYNC_BATCH_SIZE",
    )
    sqns_sync_visits_window_days: int = Field(
        default=30,
        ge=1,
        le=365,
        validation_alias="SQNS_SYNC_VISITS_WINDOW_DAYS",
    )
    sqns_sync_payments_window_days: int = Field(
        default=30,
        ge=1,
        le=90,
        validation_alias="SQNS_SYNC_PAYMENTS_WINDOW_DAYS",
    )

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        validation_alias="CORS_ORIGINS",
    )

    @field_validator("auth_api_keys", mode="before")
    @classmethod
    def parse_auth_api_keys(cls, value: Any) -> dict[str, dict[str, Any]]:
        if value is None or value == "":
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("AUTH_API_KEYS must be valid JSON") from exc
            if not isinstance(parsed, dict):
                raise ValueError("AUTH_API_KEYS must be a JSON object")
            return parsed
        raise ValueError("AUTH_API_KEYS must be a JSON object")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return ["http://localhost:3000", "http://127.0.0.1:3000"]

        if isinstance(value, list):
            origins = [str(item).strip() for item in value if str(item).strip()]
        elif isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise ValueError("CORS_ORIGINS must be valid JSON") from exc
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS must be a JSON array")
                origins = [str(item).strip() for item in parsed if str(item).strip()]
            else:
                origins = [item.strip() for item in raw.split(",") if item.strip()]
        else:
            raise ValueError("CORS_ORIGINS must be a list, JSON array or comma-separated string")

        if any(origin == "*" for origin in origins):
            raise ValueError("CORS_ORIGINS must not contain '*' when credential cookies are enabled")
        return origins

    @field_validator("auth_refresh_cookie_samesite", mode="before")
    @classmethod
    def normalize_cookie_samesite(cls, value: Any) -> str:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"lax", "strict", "none"}:
                return normalized
        raise ValueError("AUTH_REFRESH_COOKIE_SAMESITE must be one of: lax, strict, none")

    @field_validator("auth_refresh_cookie_domain", mode="before")
    @classmethod
    def normalize_cookie_domain(cls, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        raise ValueError("AUTH_REFRESH_COOKIE_DOMAIN must be a string or null")

    def get_invite_link_base(self) -> str:
        return self.invite_link_base_url or self.public_base_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
