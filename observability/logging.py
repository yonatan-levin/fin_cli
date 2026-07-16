"""Structured JSON logging with correlation-id stamping (stdlib logging only).

Mirrors midas's zap JSON encoder: keys ``ts`` / ``level`` / ``logger`` / ``msg``
plus ``request_id`` and any bound extras. No third-party logging dependency — a
small JSON formatter plus a ``logging.Filter`` that reads the contextvar. The
file sink is always JSON (midas parity) so log-ingestion pipelines can parse it
even when the console sink is human-readable.

Core module — stdlib only.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import logging.handlers
import sys
from typing import Any, TextIO

from .context import get_extra, get_request_id

# LogRecord attributes that are structural, not user fields. Anything else on a
# record (passed via ``extra=``) is emitted as a top-level JSON field.
_RESERVED = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)

_MARK = "_observability_handler"


class ContextFilter(logging.Filter):
    """Stamp request_id (+ bound extras) from the contextvar onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        for key, value in get_extra().items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = _dt.datetime.fromtimestamp(record.created, tz=_dt.UTC)
        payload: dict[str, Any] = {
            "ts": ts.isoformat().replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str, ensure_ascii=False)


_CONSOLE_FMT = "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s"


def configure_logging(
    *,
    level: str = "info",
    fmt: str = "json",
    logger_name: str | None = None,
    stream: TextIO = sys.stdout,
    file_path: str | None = None,
    file_max_bytes: int = 100 * 1024 * 1024,
    file_backups: int = 10,
) -> logging.Logger:
    """Configure a logger with a JSON (or console) stdout sink + optional rotating
    JSON file sink, both stamped with the correlation id.

    Idempotent: re-invoking replaces only the handlers this function installed, so
    it is safe to call from both the API startup and the CLI entrypoint.
    ``logger_name`` targets a named logger (e.g. the service root) and disables
    propagation; ``None`` configures the process root logger.
    """
    logger = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    logger.setLevel(_level(level))
    for handler in list(logger.handlers):
        if getattr(handler, _MARK, False):
            logger.removeHandler(handler)

    formatter: logging.Formatter = (
        JsonFormatter() if fmt == "json" else logging.Formatter(_CONSOLE_FMT)
    )
    ctx = ContextFilter()

    stream_handler = logging.StreamHandler(stream)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(ctx)
    setattr(stream_handler, _MARK, True)
    logger.addHandler(stream_handler)

    if file_path:
        file_handler = logging.handlers.RotatingFileHandler(
            file_path, maxBytes=file_max_bytes, backupCount=file_backups, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())  # file sink is always JSON
        file_handler.addFilter(ctx)
        setattr(file_handler, _MARK, True)
        logger.addHandler(file_handler)

    if logger_name:
        logger.propagate = False
    return logger


def _level(level: str) -> int:
    return int(getattr(logging, level.upper(), logging.INFO))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
