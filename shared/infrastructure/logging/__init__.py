"""
Shared infrastructure logging module.

This module provides the unified logging system for the AlgoBeta project,
combining structured logging with legacy features like colorized output and typing simulation.
"""

from .log_manager import (
    get_logger,
    log_manager,
    log_event,
    JsonFormatter,
    StructuredLogger,
    LogManager,
    VERBOSE,
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)

from .enhanced_formatters import (
    AlgoEnhancedFormatter,
    EnhancedJsonFormatter,
    LegacyCompatFormatter,
    remove_color_codes,
)

from .enhanced_handlers import (
    EnhancedConsoleHandler,
    EnhancedJsonFileHandler,
    StructuredFileHandler,
)

__all__ = [
    "get_logger",
    "log_manager",
    "log_event",
    "JsonFormatter",
    "StructuredLogger",
    "LogManager",
    "VERBOSE",
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
    "AlgoEnhancedFormatter",
    "EnhancedJsonFormatter",
    "LegacyCompatFormatter",
    "remove_color_codes",
    "EnhancedConsoleHandler",
    "EnhancedJsonFileHandler",
    "StructuredFileHandler",
]
