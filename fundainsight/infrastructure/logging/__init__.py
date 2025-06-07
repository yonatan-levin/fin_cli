"""
Fundainsight logging module - DEPRECATED.

This module has been moved to shared/infrastructure/logging/.
This file provides backward compatibility by importing from the shared system.
"""

# Import everything from the new shared location
from shared.infrastructure.logging import *

# Maintain backward compatibility
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
]
