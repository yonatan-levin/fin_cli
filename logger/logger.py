"""Logging module for AlgoBeta - Enhanced with shared infrastructure."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from colorama import Fore

if TYPE_CHECKING:
    from ..config.config import Config

from singleton import Singleton
from shared.infrastructure.logging import get_logger as get_shared_logger, log_manager

from .formatters import AlgoFormatter, JsonFormatter
from .handlers import ConsoleHandler, JsonFileHandler, TypingConsoleHandler


class Logger(metaclass=Singleton):
    """
    Logger that handle titles in different colors.
    Outputs logs in console, activity.log, and errors.log
    For console handler: simulates typing

    Enhanced to use shared logging infrastructure while maintaining backward compatibility.
    """

    def __init__(self):
        # create log directory if it doesn't exist
        # TODO: use workdir from config
        self.log_dir = Path(__file__).parent.parent.parent / "logs"
        if not self.log_dir.exists():
            self.log_dir.mkdir()

        log_file = "activity.log"
        error_file = "error.log"

        console_formatter = AlgoFormatter("%(title_color)s %(message)s")

        # Create a handler for console which simulate typing
        self.typing_console_handler = TypingConsoleHandler()
        self.typing_console_handler.setLevel(logging.INFO)
        self.typing_console_handler.setFormatter(console_formatter)

        # Create a handler for console without typing simulation
        self.console_handler = ConsoleHandler()
        self.console_handler.setLevel(logging.DEBUG)
        self.console_handler.setFormatter(console_formatter)

        # Info handler in activity.log
        self.file_handler = logging.FileHandler(
            self.log_dir / log_file, "a", "utf-8")
        self.file_handler.setLevel(logging.DEBUG)
        info_formatter = AlgoFormatter(
            "%(asctime)s %(levelname)s %(title)s %(message_no_color)s"
        )
        self.file_handler.setFormatter(info_formatter)

        # Error handler error.log
        error_handler = logging.FileHandler(
            self.log_dir / error_file, "a", "utf-8")
        error_handler.setLevel(logging.ERROR)
        error_formatter = AlgoFormatter(
            "%(asctime)s %(levelname)s %(module)s:%(funcName)s:%(lineno)d %(title)s"
            " %(message_no_color)s"
        )
        error_handler.setFormatter(error_formatter)

        self.typing_logger = logging.getLogger("TYPER")
        self.typing_logger.addHandler(self.typing_console_handler)
        self.typing_logger.addHandler(self.file_handler)
        self.typing_logger.addHandler(error_handler)
        self.typing_logger.setLevel(logging.DEBUG)

        self.logger = logging.getLogger("LOGGER")
        self.logger.addHandler(self.console_handler)
        self.logger.addHandler(self.file_handler)
        self.logger.addHandler(error_handler)
        self.logger.setLevel(logging.DEBUG)

        self.json_logger = logging.getLogger("JSON_LOGGER")
        self.json_logger.addHandler(self.file_handler)
        self.json_logger.addHandler(error_handler)
        self.json_logger.setLevel(logging.DEBUG)

        # Enhanced structured logger from shared infrastructure
        self.structured_logger = get_shared_logger("STRUCTURED_LOGGER")

        self._config: Optional[Config] = None
        self.chat_plugins = []

    @property
    def config(self) -> Config | None:
        return self._config

    @config.setter
    def config(self, config: Config):
        self._config = config

    def debug(
        self,
        message: str,
        title: str = "",
        title_color: str = "",
        context: Optional[dict] = None,
    ) -> None:
        """
        Log a debug message with optional context.

        Args:
            message: The message to log
            title: Optional title for the message  
            title_color: Optional color for the title
            context: Optional context data for structured logging
        """
        self._log(title, title_color, message, logging.DEBUG)
        # Also log to structured logger if context provided
        if context:
            self.structured_logger.debug(f"{title} {message}", context=context)

    def info(
        self,
        message: str,
        title: str = "",
        title_color: str = "",
        context: Optional[dict] = None,
    ) -> None:
        """
        Log an info message with optional context.

        Args:
            message: The message to log
            title: Optional title for the message  
            title_color: Optional color for the title
            context: Optional context data for structured logging
        """
        self._log(title, title_color, message, logging.INFO)
        # Also log to structured logger if context provided
        if context:
            self.structured_logger.info(f"{title} {message}", context=context)

    def warn(
        self,
        message: str,
        title: str = "",
        title_color: str = "",
        context: Optional[dict] = None,
    ) -> None:
        """
        Log a warning message with optional context.

        Args:
            message: The message to log
            title: Optional title for the message  
            title_color: Optional color for the title
            context: Optional context data for structured logging
        """
        self._log(title, title_color, message, logging.WARN)
        # Also log to structured logger if context provided
        if context:
            self.structured_logger.warning(
                f"{title} {message}", context=context)

    def error(self, title: str, message: str = "", context: Optional[dict] = None) -> None:
        """
        Log an error message with optional context.

        Args:
            title: The error title
            message: Optional error message
            context: Optional context data for structured logging
        """
        self._log(title, Fore.RED, message, logging.ERROR)
        # Also log to structured logger if context provided
        if context:
            self.structured_logger.error(f"{title} {message}", context=context)

    def _log(
        self,
        title: str = "",
        title_color: str = "",
        message: str = "",
        level: int = logging.INFO,
    ) -> None:
        if message:
            if isinstance(message, list):
                message = " ".join(message)
        self.logger.log(
            level, message, extra={"title": str(
                title), "color": str(title_color)}
        )

    def set_level(self, level: logging._Level) -> None:
        self.logger.setLevel(level)
        self.typing_logger.setLevel(level)
        self.structured_logger.setLevel(level)

    def double_check(self, additionalText: Optional[str] = None) -> None:
        if not additionalText:
            additionalText = (
                "Please ensure you've setup and configured everything"
                " correctly. Read https://github.com/Torantulino/Auto-GPT#readme to "
                "double check. You can also create a github issue or join the discord"
                " and ask there!"
            )

    def log_json(self, data: Any, file_name: str | Path) -> None:
        # Create a handler for JSON files
        json_file_path = self.log_dir / file_name
        json_data_handler = JsonFileHandler(json_file_path)
        json_data_handler.setFormatter(JsonFormatter())

        # Log the JSON data using the custom file handler
        self.json_logger.addHandler(json_data_handler)
        self.json_logger.debug(data)
        self.json_logger.removeHandler(json_data_handler)

    # New enhanced methods that expose structured logging capabilities
    def log_event(self, event_type: str, **kwargs) -> None:
        """
        Log a structured event.

        Args:
            event_type: Type of event
            **kwargs: Event data
        """
        context = {"event_type": event_type, "event_data": kwargs}
        self.structured_logger.info(f"Event: {event_type}", context=context)

    def configure_shared_logging(
        self,
        level: int = logging.INFO,
        log_format: str = "json",
        log_dir: Optional[str] = None,
        max_size_mb: int = 10,
        backup_count: int = 5,
        console: bool = True,
    ) -> None:
        """
        Configure the shared logging system.

        Args:
            level: Minimum log level
            log_format: Output format ('json' or 'text')
            log_dir: Directory for log files (None for no file logging)
            max_size_mb: Maximum size of log files in MB
            backup_count: Number of backup files to keep
            console: Whether to log to console
        """
        log_manager.configure(
            level=level,
            log_format=log_format,
            log_dir=log_dir,
            max_size_mb=max_size_mb,
            backup_count=backup_count,
            console=console
        )


logger = Logger()
