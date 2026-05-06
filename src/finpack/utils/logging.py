"""Logging utilities for finpack.

This module provides explicit configuration helpers that avoid import-time
side effects. Callers are responsible for invoking :func:`configure_logging`
when logging behaviour is required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


# NOTE: Module-level registries intentionally stay private to avoid accidental
# cross-module mutations. They are reset explicitly via ``reset_logging`` to
# support deterministic tests.
_LOGGER_REGISTRY: Dict[str, logging.Logger] = {}
_IS_CONFIGURED: bool = False


@dataclass(slots=True)
class FinPackConfig:
    """Configuration object for finpack logging.

    Attributes:
        log_level: Desired logging level.
        log_to_console: Whether to emit logs to the console.
        log_to_file: Whether to emit logs to a file.
        log_file_name: File name to use when ``log_to_file`` is enabled.
        log_directory: Directory that hosts the log files; required when
            ``log_to_file`` is true.
    """

    log_level: str = "INFO"
    log_to_console: bool = True
    log_to_file: bool = False
    log_file_name: str = "finpack.log"
    log_directory: Optional[Path] = None


def configure_logging(config: FinPackConfig) -> logging.Logger:
    """Configure finpack logging explicitly.

    Returns the root finpack logger instance. Calling this function multiple
    times replaces the existing configuration.
    """

    global _IS_CONFIGURED

    reset_logging()

    logger = logging.getLogger("finpack")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    logger.propagate = False

    handlers = []

    if config.log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logger.level)
        logger.addHandler(console_handler)
        handlers.append(console_handler)

    if config.log_to_file:
        if config.log_directory is None:
            raise ValueError("log_directory must be provided when log_to_file is True")

        config.log_directory.mkdir(parents=True, exist_ok=True)
        file_path = config.log_directory / config.log_file_name
        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(logger.level)
        logger.addHandler(file_handler)
        handlers.append(file_handler)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    for handler in handlers:
        handler.setFormatter(formatter)

    _LOGGER_REGISTRY[logger.name] = logger
    _IS_CONFIGURED = True
    return logger


def get_logger(name: str = "finpack") -> logging.Logger:
    """Fetch the configured finpack logger.

    Calling this function prior to :func:`configure_logging` returns an
    unconfigured logger. This allows code to create loggers without triggering
    implicit configuration.
    """

    if name in _LOGGER_REGISTRY:
        return _LOGGER_REGISTRY[name]

    logger = logging.getLogger(name)
    _LOGGER_REGISTRY[name] = logger
    return logger


def reset_logging() -> None:
    """Reset configured loggers to a clean state.

    This helper makes tests deterministic and allows reconfiguration at runtime.
    """

    global _IS_CONFIGURED

    for logger in _LOGGER_REGISTRY.values():
        handlers = list(logger.handlers)
        for handler in handlers:
            handler.close()
            logger.removeHandler(handler)

    _LOGGER_REGISTRY.clear()
    _IS_CONFIGURED = False


def is_logging_configured() -> bool:
    """Return whether logging was explicitly configured."""

    return _IS_CONFIGURED

