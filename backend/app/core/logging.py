from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


_WAPPI_WEBHOOK_LOG_FILES: dict[str, Path] = {
    "webhooks.wappi": Path("/logs/webhooks_wappi.log"),
    "webhooks.wappi.telegram": Path("/logs/webhooks_wappi_telegram.log"),
    "webhooks.wappi.whatsapp": Path("/logs/webhooks_wappi_whatsapp.log"),
    "webhooks.wappi.max": Path("/logs/webhooks_wappi_max.log"),
}


def bind_trace_id(trace_id: str | None) -> None:
    if trace_id is None:
        return
    structlog.contextvars.bind_contextvars(trace_id=trace_id)


def get_trace_id() -> str | None:
    return structlog.contextvars.get_contextvars().get("trace_id")


def configure_logging() -> None:
    # Путь к файлу логов (внутри контейнера папка монтируется в /logs)
    log_file = Path("/logs/api_requests.log")
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    # Добавляем запись в файл, если папка существует
    if log_file.parent.exists():
        file_handler = logging.FileHandler(log_file)
        handlers.append(file_handler)

    logging.basicConfig(
        level=logging.INFO, 
        format="%(message)s",
        handlers=handlers,
        force=True
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    _configure_webhook_logger()
    _configure_wappi_webhook_logger()


def _configure_webhook_logger() -> None:
    log_file = Path("/logs/webhooks.log")
    if not log_file.parent.exists():
        return
    logger = logging.getLogger("webhooks")
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_file:
            return
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    logger.propagate = False


def _configure_wappi_webhook_logger() -> None:
    for logger_name, log_file in _WAPPI_WEBHOOK_LOG_FILES.items():
        _configure_file_logger(logger_name, log_file)


def _configure_file_logger(logger_name: str, log_file: Path) -> None:
    if not log_file.parent.exists():
        return
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename) == log_file:
            return
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    logger.propagate = False
