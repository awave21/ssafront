from __future__ import annotations

from typing import Any
import base64
import json
import time
from urllib.parse import urlparse

import httpx
import structlog
from jsonschema import Draft202012Validator, ValidationError
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.schemas.auth import AuthContext
from app.services.secrets import resolve_secret
from app.utils.idempotency import generate_idempotency_key

logger = structlog.get_logger(__name__)


class ToolExecutionError(Exception):
    pass


def _resolve_url_templates(
    endpoint_template: str,
    args: dict[str, Any],
) -> tuple[str, set[str]]:
    """
    Подставить {{var}} шаблоны в URL (path + query string).

    Возвращает (resolved_url, used_keys) — ключи, которые были
    подставлены в URL и не нуждаются в дальнейшей маршрутизации.
    """
    resolved = endpoint_template
    used: set[str] = set()
    for arg_name, arg_value in args.items():
        placeholder = "{{" + arg_name + "}}"
        if placeholder in resolved:
            resolved = resolved.replace(placeholder, str(arg_value))
            used.add(arg_name)
    return resolved, used


def _split_params(
    endpoint_template: str,
    args: dict[str, Any],
    parameter_mapping: dict[str, str] | None,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """
    Разделить args на path/query/body по parameter_mapping.

    Поддерживает два вида шаблонов в URL:
      - {{var}} — подставляется в любое место URL (path, query string)
      - {var}  — классический path-параметр (/users/{id})

    Возвращает (resolved_url, query_params, body_params).
    """
    # 1. Подставить {{var}} шаблоны (работает везде в URL)
    resolved_url, used_in_template = _resolve_url_templates(endpoint_template, args)

    path_params: dict[str, Any] = {}
    query_params: dict[str, Any] = {}
    body_params: dict[str, Any] = {}

    if not parameter_mapping:
        # Без маппинга — неиспользованные args идут в body (обратная совместимость)
        remaining = {k: v for k, v in args.items() if k not in used_in_template}
        return resolved_url, {}, remaining

    for arg_name, arg_value in args.items():
        if arg_name in used_in_template:
            continue  # уже подставлен в URL через {{var}}
        target = parameter_mapping.get(arg_name, "body")
        if target == "path":
            path_params[arg_name] = arg_value
        elif target == "query":
            query_params[arg_name] = arg_value
        else:  # body or header
            body_params[arg_name] = arg_value

    # 2. Подставить {var} path-параметры: /api/users/{user_id} → /api/users/123
    for key, value in path_params.items():
        resolved_url = resolved_url.replace(f"{{{key}}}", str(value))

    return resolved_url, query_params, body_params


def _resolve_path(data: Any, path: str) -> Any:
    """
    Извлечь значение по dot-path с поддержкой массивов.
    
    Примеры:
      "data.total" → data["total"]
      "data.orders[].id" → [order["id"] for order in data["orders"]]
      "data.orders[].customer.name" → [order["customer"]["name"] for ...]
    """
    if not path:
        return data
    
    parts = path.split(".")
    current = data
    
    for i, part in enumerate(parts):
        if current is None:
            return None
            
        # Проверить, есть ли [] в конце части
        if part.endswith("[]"):
            # Убрать [] и получить имя массива
            array_name = part[:-2]
            current = current.get(array_name) if isinstance(current, dict) else None
            
            if not isinstance(current, list):
                return None
            
            # Если есть ещё части пути — рекурсивно применить к каждому элементу
            remaining_path = ".".join(parts[i + 1:])
            if remaining_path:
                return [_resolve_path(item, remaining_path) for item in current]
            else:
                # Если это последняя часть — вернуть весь массив
                return current
        else:
            # Обычное поле
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
    
    return current


def _pick_fields(obj: dict[str, Any], field_defs: list[dict[str, str]]) -> dict[str, Any]:
    """Извлечь выбранные поля из одного объекта."""
    result: dict[str, Any] = {}
    for field_def in field_defs:
        source = field_def.get("source")
        target = field_def.get("target")
        if source and target:
            result[target] = _resolve_path(obj, source)
    return result


def transform_response(raw: Any, config: dict[str, Any] | None) -> Any:
    """
    Применить response_transform к ответу API.

    Универсальная обработка:
    - Если raw это dict — фильтруем поля объекта
    - Если raw это list — фильтруем поля каждого элемента
    - jmespath работает с любой структурой
    """
    if not config:
        return raw

    mode = config.get("mode")

    if mode == "jmespath":
        try:
            import jmespath
            expression = config.get("expression", "@")
            return jmespath.search(expression, raw)
        except Exception as e:
            logger.warning("jmespath_transform_error", error=str(e))
            return raw

    if mode == "fields":
        try:
            field_defs = config.get("fields", [])
            array_defs = config.get("arrays", [])

            # ── Корневой ответ — массив объектов ──
            if isinstance(raw, list):
                if not field_defs:
                    return raw
                return [_pick_fields(item, field_defs) for item in raw if isinstance(item, dict)]

            # ── Корневой ответ — объект ──
            if isinstance(raw, dict):
                result: dict[str, Any] = {}

                # Обычные поля верхнего уровня
                if field_defs:
                    result = _pick_fields(raw, field_defs)

                # Вложенные массивы (например data.orders[])
                for array_def in array_defs:
                    source = array_def.get("source")
                    target = array_def.get("target")
                    nested_fields = array_def.get("fields", [])

                    if not source or not target:
                        continue

                    source_array = _resolve_path(raw, source)
                    if not isinstance(source_array, list):
                        continue

                    if nested_fields:
                        result[target] = [
                            _pick_fields(item, nested_fields)
                            for item in source_array
                            if isinstance(item, dict)
                        ]
                    else:
                        # Без fields — оставить массив как есть
                        result[target] = source_array

                return result

            # Примитив (строка, число) — вернуть как есть
            return raw
        except Exception as e:
            logger.warning("fields_transform_error", error=str(e))
            return raw

    return raw


def _ensure_allowed_domain(endpoint: str, allowed_domains: list[str] | None) -> None:
    if not allowed_domains:
        return
    hostname = urlparse(endpoint).hostname
    if hostname is None or hostname not in allowed_domains:
        raise ToolExecutionError("Endpoint domain is not allowed")


def _validate_args(schema: dict[str, Any], args: dict[str, Any]) -> None:
    try:
        Draft202012Validator(schema).validate(args)
    except ValidationError as exc:
        raise ToolExecutionError(f"Invalid tool arguments: {exc.message}") from exc


def _parse_secret_payload(secret: str | None) -> str | dict[str, Any] | None:
    if secret is None:
        return None
    trimmed = secret.strip()
    if not trimmed:
        return None
    if trimmed.startswith("{") and trimmed.endswith("}"):
        try:
            parsed = json.loads(trimmed)
        except json.JSONDecodeError:
            return secret
        if isinstance(parsed, dict):
            return parsed
        return secret
    return secret


def _apply_auth(
    auth_type: str,
    secret_payload: dict[str, Any] | str | None,
    headers: dict[str, str],
    query_params: dict[str, Any],
) -> None:
    """Применить аутентификацию к headers/query_params на основе auth_type и secret_payload.

    Мутирует headers и query_params in-place.
    """
    if auth_type == "api_key":
        if not secret_payload:
            raise ToolExecutionError("Missing API key secret")
        if isinstance(secret_payload, dict):
            header_name = str(secret_payload.get("header") or "x-api-key")
            header_value = secret_payload.get("value")
            if not header_value:
                raise ToolExecutionError("Missing API key secret value")
            headers[header_name] = str(header_value)
        else:
            headers["x-api-key"] = str(secret_payload)
    elif auth_type == "bearer_token":
        if not secret_payload:
            raise ToolExecutionError("Missing bearer token secret")
        if isinstance(secret_payload, dict):
            token = secret_payload.get("token") or secret_payload.get("value")
        else:
            token = secret_payload
        if not token:
            raise ToolExecutionError("Missing bearer token value")
        headers["Authorization"] = f"Bearer {token}"
    elif auth_type == "basic_auth":
        if not secret_payload:
            raise ToolExecutionError("Missing basic auth secret")
        if isinstance(secret_payload, dict):
            username = secret_payload.get("username")
            password = secret_payload.get("password")
        else:
            if ":" not in secret_payload:
                raise ToolExecutionError("basic_auth secret must be 'username:password' or JSON object")
            username, password = secret_payload.split(":", 1)
        if not username or not password:
            raise ToolExecutionError("basic_auth secret must include username and password")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"
    elif auth_type == "custom_header":
        if not isinstance(secret_payload, dict):
            raise ToolExecutionError("custom_header secret must be JSON object")
        headers.update({str(key): str(value) for key, value in secret_payload.items()})
    elif auth_type == "query_param":
        if not secret_payload:
            raise ToolExecutionError("Missing query param secret")
        if isinstance(secret_payload, dict):
            param_name = str(secret_payload.get("name") or "api_key")
            param_value = secret_payload.get("value")
            if not param_value:
                raise ToolExecutionError("Missing query param value")
            query_params[param_name] = param_value
        else:
            query_params["api_key"] = str(secret_payload)
    elif auth_type in {"oauth2", "service"}:
        raise ToolExecutionError(f"auth_type '{auth_type}' is not implemented")
    elif auth_type != "none":
        raise ToolExecutionError("Unsupported tool auth type")


async def execute_tool_call(
    endpoint: str,
    input_schema: dict[str, Any],
    args: dict[str, Any],
    *,
    trace_id: str,
    auth_type: str,
    http_method: str = "POST",
    parameter_mapping: dict[str, str] | None = None,
    custom_headers: dict[str, str] | None = None,
    secrets_ref: str | None,
    secret_payload: dict[str, Any] | str | None = None,
    allowed_domains: list[str] | None,
    timeout_ms: int | None,
    user: AuthContext,
) -> Any:
    settings = get_settings()
    _validate_args(input_schema, args)

    headers = {
        "x-trace-id": trace_id,
        "x-idempotency-key": generate_idempotency_key(),
        "x-tenant-id": str(user.tenant_id),
        "x-user-id": str(user.user_id),
    }
    if custom_headers:
        headers.update(custom_headers)

    if secret_payload is None:
        secret_payload = _parse_secret_payload(resolve_secret(secrets_ref))
    elif isinstance(secret_payload, str):
        secret_payload = _parse_secret_payload(secret_payload)
    query_params: dict[str, Any] = {}

    _apply_auth(auth_type, secret_payload, headers, query_params)

    timeout = (timeout_ms or settings.tool_default_timeout_ms) / 1000.0
    timeout = min(timeout, settings.tool_max_timeout_ms / 1000.0)

    # Разделить параметры на path/query/body
    resolved_url, extra_query, body = _split_params(endpoint, args, parameter_mapping)
    all_query = {**query_params, **extra_query}
    
    # Валидация resolved_url (после подстановки path params)
    _ensure_allowed_domain(resolved_url, allowed_domains)

    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(settings.tool_retry_attempts + 1),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)),
        reraise=True,
    ):
        with attempt:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Подготовить аргументы запроса
                request_kwargs: dict[str, Any] = {
                    "params": all_query or None,
                    "headers": headers,
                }
                # Body только для методов, которые его поддерживают
                if http_method.upper() in ("POST", "PUT", "PATCH") and body:
                    request_kwargs["json"] = body
                
                response = await client.request(http_method.upper(), resolved_url, **request_kwargs)
                
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        "Tool server error",
                        request=response.request,
                        response=response,
                    )
                if response.status_code >= 400:
                    raise ToolExecutionError(f"Tool error {response.status_code}: {response.text}")
                try:
                    payload = response.json()
                except ValueError:
                    payload = response.text
                logger.info(
                    "tool_call",
                    endpoint=resolved_url,
                    method=http_method.upper(),
                    status_code=response.status_code,
                    trace_id=trace_id,
                )
                return payload

    raise ToolExecutionError("Tool call failed")


async def execute_tool_test(
    endpoint: str,
    args: dict[str, Any],
    *,
    http_method: str = "POST",
    parameter_mapping: dict[str, str] | None = None,
    auth_type: str = "none",
    secret_payload: dict[str, Any] | str | None = None,
    custom_headers: dict[str, str] | None = None,
    response_transform: dict[str, Any] | None = None,
    timeout_ms: int | None = None,
    allowed_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Тестовый вызов tool. Возвращает полную информацию о запросе/ответе."""
    settings = get_settings()

    # Разделить параметры
    resolved_url, query_params, body = _split_params(endpoint, args, parameter_mapping)
    
    # Валидация домена
    _ensure_allowed_domain(resolved_url, allowed_domains)
    
    headers = custom_headers.copy() if custom_headers else {}
    
    # Применить auth к headers (в тестовом режиме ошибки auth не фатальны)
    if secret_payload is None:
        secret_payload = ""
    elif isinstance(secret_payload, str):
        secret_payload = _parse_secret_payload(secret_payload)
    
    auth_query_params: dict[str, Any] = {}
    try:
        _apply_auth(auth_type, secret_payload or None, headers, auth_query_params)
    except ToolExecutionError:
        # В тестовом режиме пропускаем ошибки auth — пользователь может тестировать без секретов
        pass
    
    all_query = {**query_params, **auth_query_params}
    
    timeout = (timeout_ms or settings.tool_default_timeout_ms) / 1000.0
    timeout = min(timeout, settings.tool_max_timeout_ms / 1000.0)
    
    start = time.monotonic()
    error_msg = None
    status_code = 0
    response_headers = {}
    raw_body = None
    raw_size = 0
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            request_kwargs: dict[str, Any] = {
                "params": all_query or None,
                "headers": headers,
            }
            if http_method.upper() in ("POST", "PUT", "PATCH") and body:
                request_kwargs["json"] = body
            
            response = await client.request(http_method.upper(), resolved_url, **request_kwargs)
            
            status_code = response.status_code
            response_headers = dict(response.headers)
            raw_size = len(response.content)
            
            # Попытка распарсить JSON
            content_type = response.headers.get("content-type", "")
            if "json" in content_type:
                try:
                    raw_body = response.json()
                except ValueError:
                    raw_body = response.text
            else:
                raw_body = response.text
    
    except httpx.TimeoutException:
        error_msg = f"Timed out after {timeout} seconds"
    except httpx.RequestError as e:
        error_msg = f"Request error: {str(e)}"
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
    
    latency = int((time.monotonic() - start) * 1000)
    
    # Применить transform если нужно и если есть raw_body
    transformed_body = None
    transformed_size = None
    if response_transform and raw_body and not error_msg:
        try:
            transformed_body = transform_response(raw_body, response_transform)
            transformed_size = len(json.dumps(transformed_body).encode("utf-8"))
        except Exception as e:
            logger.warning("test_transform_error", error=str(e))
    
    return {
        "status_code": status_code,
        "latency_ms": latency,
        "response_headers": response_headers,
        "raw_body": raw_body,
        "transformed_body": transformed_body,
        "raw_size_bytes": raw_size,
        "transformed_size_bytes": transformed_size,
        "error": error_msg,
        "request_url": resolved_url,
        "request_method": http_method.upper(),
    }
