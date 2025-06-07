"""
Shared log manager module.

This module provides enhanced logging capabilities for the AlgoBeta application,
including structured logging, log rotation, and standardized formatting.
Consolidates logging functionality from both fincli and fundainsight modules.
"""
import datetime
import json
import logging
import logging.handlers
import os
import sys
from typing import Any, Dict, Optional, Union, cast

# Create custom log levels
VERBOSE = 15
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# Register custom log levels
logging.addLevelName(VERBOSE, "VERBOSE")


class StructuredLogRecord(logging.LogRecord):
    """Enhanced LogRecord with additional context data."""

    def __init__(self, name, level, pathname, lineno, msg, args, exc_info, func=None, sinfo=None):
        super().__init__(name, level, pathname, lineno, msg, args, exc_info, func, sinfo)
        self.context: Dict[str, Any] = {}


class StructuredLogger(logging.Logger):
    """Enhanced Logger that supports structured logging."""

    def makeRecord(self, name, level, fn, lno, msg, args, exc_info, func=None, extra=None, sinfo=None):
        """Create a LogRecord with context data."""
        # Create a standard LogRecord first, then convert to StructuredLogRecord
        standard_record = super().makeRecord(name, level, fn, lno, msg,
                                             args, exc_info, func, extra, sinfo)
        # Create our StructuredLogRecord with the same parameters
        # fn corresponds to pathname in LogRecord constructor
        record = StructuredLogRecord(
            name, level, fn, lno, msg, args, exc_info, func, sinfo)
        # Copy all attributes from the standard record
        record.__dict__.update(standard_record.__dict__)

        if extra is not None:
            for key in extra:
                if key in ["message", "asctime", "levelname", "levelno"]:
                    # Skip reserved keys
                    continue
                if key == "context" and extra[key] is not None:
                    # Handle context dict safely
                    try:
                        # Safely copy items from the context dict to record.context
                        # Convert to dict if possible
                        extra_context = dict(extra[key])
                        for context_key, context_value in extra_context.items():
                            record.context[context_key] = context_value
                    except (TypeError, ValueError):
                        # If conversion fails, skip context merging
                        pass
                else:
                    setattr(record, key, extra[key])
        return record

    def _log_with_context(self, level, msg, context=None, *args, **kwargs):
        """Log with additional context."""
        extra = kwargs.get("extra", {})
        extra_context = extra.get("context", {})
        if context and isinstance(context, dict):
            if "context" not in extra:
                extra["context"] = {}
            extra["context"].update(context)
        if extra_context:
            if "context" not in extra:
                extra["context"] = {}
            extra["context"].update(extra_context)
        kwargs["extra"] = extra
        self._log(level, msg, args, **kwargs)

    def debug(self, msg, *args, context=None, **kwargs):
        """
        Log a debug message with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        self._log_with_context(DEBUG, msg, context, *args, **kwargs)

    def verbose(self, msg, *args, context=None, **kwargs):
        """
        Log a verbose message with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        self._log_with_context(VERBOSE, msg, context, *args, **kwargs)

    def info(self, msg, *args, context=None, **kwargs):
        """
        Log an info message with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        self._log_with_context(INFO, msg, context, *args, **kwargs)

    def warning(self, msg, *args, context=None, **kwargs):
        """
        Log a warning message with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        self._log_with_context(WARNING, msg, context, *args, **kwargs)

    def error(self, msg, *args, context=None, **kwargs):
        """
        Log an error message with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        self._log_with_context(ERROR, msg, context, *args, **kwargs)

    def critical(self, msg, *args, context=None, **kwargs):
        """
        Log a critical message with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        self._log_with_context(CRITICAL, msg, context, *args, **kwargs)

    def exception(self, msg, *args, context=None, **kwargs):
        """
        Log an exception with context.

        Args:
            msg: The message to log
            *args: Arguments for message formatting (standard logging compatibility)
            context: Additional context data (dict) - keyword only
            **kwargs: Additional logging parameters
        """
        kwargs.setdefault("exc_info", True)
        self._log_with_context(ERROR, msg, context, *args, **kwargs)


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: StructuredLogRecord) -> str:
        """
        Format a log record as JSON.

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

        # Add context data if available
        if hasattr(record, "context") and record.context:
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


class LogManager:
    """
    Manage application logging configuration.

    This class provides a centralized way to configure logging for the application,
    with support for different output formats and destinations.
    """

    def __init__(self):
        """Initialize the log manager."""
        # Register the custom logger class
        logging.setLoggerClass(StructuredLogger)

        self.root_logger = logging.getLogger()
        self.loggers = {}

    def configure(
        self,
        level: int = INFO,
        log_format: str = "json",
        log_dir: Optional[str] = None,
        max_size_mb: int = 10,
        backup_count: int = 5,
        console: bool = True,
    ) -> None:
        """
        Configure logging.

        Args:
            level: Minimum log level
            log_format: Output format ('json' or 'text')
            log_dir: Directory for log files (None for no file logging)
            max_size_mb: Maximum size of log files in MB
            backup_count: Number of backup files to keep
            console: Whether to log to console
        """
        # Reset existing configuration
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)

        # Set the root logger level
        self.root_logger.setLevel(level)

        # Create formatters
        if log_format.lower() == "json":
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s"
            )

        # Console handler
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.root_logger.addHandler(console_handler)

        # File handler
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            file_path = os.path.join(log_dir, "app.log")
            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
            )
            file_handler.setFormatter(formatter)
            self.root_logger.addHandler(file_handler)

    def get_logger(self, name: str) -> StructuredLogger:
        """
        Get a logger with the specified name.

        Args:
            name: Logger name

        Returns:
            StructuredLogger instance
        """
        logger = logging.getLogger(name)
        return cast(StructuredLogger, logger)


# Singleton instance
log_manager = LogManager()


def get_logger(name: str) -> StructuredLogger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name

    Returns:
        StructuredLogger instance
    """
    return log_manager.get_logger(name)


def log_event(logger: StructuredLogger, event_type: str, **kwargs) -> None:
    """
    Log a structured event.

    Args:
        logger: Logger to use
        event_type: Type of event
        **kwargs: Event data
    """
    context = {"event_type": event_type, "event_data": kwargs}
    logger.info(f"Event: {event_type}", context=context)
