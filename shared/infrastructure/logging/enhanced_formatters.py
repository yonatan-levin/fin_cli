"""
Enhanced formatters for the shared logging system.

This module provides formatters that combine the structured logging capabilities
with the legacy colorized output and custom formatting features.
"""
import logging
import re
import datetime
import json
from typing import Any, Dict

from colorama import Style

from .log_manager import StructuredLogRecord


class AlgoEnhancedFormatter(logging.Formatter):
    """
    Enhanced formatter that combines AlgoFormatter features with structured logging.
    Allows to handle custom placeholders 'title_color' and 'message_no_color'.
    To use this formatter, make sure to pass 'color', 'title' as log extras.
    """

    def format(self, record: logging.LogRecord) -> str:
        # Handle legacy title and color functionality
        if hasattr(record, "color"):
            record.title_color = (
                getattr(record, "color")
                + getattr(record, "title", "")
                + " "
                + Style.RESET_ALL
            )
        else:
            record.title_color = getattr(record, "title", "")

        # Add this line to set 'title' to an empty string if it doesn't exist
        record.title = getattr(record, "title", "")

        if hasattr(record, "msg"):
            record.message_no_color = remove_color_codes(
                getattr(record, "msg"))
        else:
            record.message_no_color = ""

        # Handle structured logging context if available
        if isinstance(record, StructuredLogRecord) and hasattr(record, "context") and record.context:
            # Add context info to the message for text output
            context_str = f" [Context: {', '.join(f'{k}={v}' for k, v in record.context.items())}]"
            if hasattr(record, "msg"):
                record.msg = str(record.msg) + context_str

        return super().format(record)


class EnhancedJsonFormatter(logging.Formatter):
    """
    Enhanced JSON formatter that combines legacy and structured logging capabilities.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format a log record as JSON with enhanced context support.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add legacy title and color information if available
        if hasattr(record, "title"):
            log_data["title"] = getattr(record, "title", "")
        if hasattr(record, "color"):
            log_data["color"] = getattr(record, "color", "")

        # Add context data if available (from structured logging)
        if isinstance(record, StructuredLogRecord) and hasattr(record, "context") and record.context:
            log_data["context"] = record.context

        # Add exception info if available
        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type is not None:
                log_data["exception"] = {
                    "type": exc_type.__name__,
                    "message": str(record.exc_info[1]),
                    "traceback": self.formatException(record.exc_info),
                }

        return json.dumps(log_data)


class LegacyCompatFormatter(logging.Formatter):
    """
    Formatter that maintains exact compatibility with the legacy JsonFormatter.
    """

    def format(self, record: logging.LogRecord):
        return record.msg


def remove_color_codes(s: str) -> str:
    """Remove ANSI color codes from a string."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", s)
