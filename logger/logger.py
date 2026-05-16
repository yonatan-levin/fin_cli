"""Logging module for Auto-GPT."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

from colorama import Fore

if TYPE_CHECKING:
    from ..config.config import Config

from singleton import Singleton

from .formatters import AlgoFormatter, JsonFormatter
from .handlers import ConsoleHandler, JsonFileHandler, TypingConsoleHandler


class Logger(metaclass=Singleton):
    """
    Logger that handle titles in different colors.
    Outputs logs in console, activity.log, and errors.log
    For console handler: simulates typing
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
        self.file_handler = logging.FileHandler(self.log_dir / log_file, "a", "utf-8")
        self.file_handler.setLevel(logging.DEBUG)
        info_formatter = AlgoFormatter("%(asctime)s %(levelname)s %(title)s %(message_no_color)s")
        self.file_handler.setFormatter(info_formatter)

        # Error handler error.log
        error_handler = logging.FileHandler(self.log_dir / error_file, "a", "utf-8")
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

        self._config: Config | None = None
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
    ) -> None:
        self._log(title, title_color, message, logging.DEBUG)

    def info(
        self,
        message: str,
        title: str = "",
        title_color: str = "",
    ) -> None:
        self._log(title, title_color, message, logging.INFO)

    def warn(
        self,
        message: str,
        title: str = "",
        title_color: str = "",
    ) -> None:
        self._log(title, title_color, message, logging.WARN)

    def error(self, title: str, message: str = "") -> None:
        self._log(title, Fore.RED, message, logging.ERROR)

    def _log(
        self,
        title: str = "",
        title_color: str = "",
        message: str = "",
        level: int = logging.INFO,
    ) -> None:
        if message and isinstance(message, list):
            message = " ".join(message)
        self.logger.log(level, message, extra={"title": str(title), "color": str(title_color)})

    def set_level(self, level: logging._Level) -> None:
        self.logger.setLevel(level)
        self.typing_logger.setLevel(level)

    def set_console_stream(self, stream: IO[str]) -> None:
        """Retarget the two console handlers (typing-effect + plain) to `stream`.

        Pillar 2's ``--output -`` mode requires CSV bytes to be the **only**
        thing on stdout. The two human-readable console handlers normally
        write to stdout, so this method exists to reroute them to ``stderr``
        (or any other text-mode stream) before the CSV write begins. File
        handlers (``activity.log``, ``error.log``) are unaffected — only the
        in-process console stream changes.

        Args:
            stream: A text-mode file-like object with a writable ``write``
                method (e.g., ``sys.stderr``, an ``io.StringIO`` for tests).
        """
        # The handlers extend ``logging.StreamHandler`` and our custom
        # ``emit`` methods route through ``self.stream``, so updating the
        # attribute here is sufficient to retarget both handlers' output.
        self.typing_console_handler.stream = stream
        self.console_handler.stream = stream

    def set_quiet(self, quiet: bool) -> None:
        """Toggle the console-suppression flag for the two console handlers.

        Pillar 3's ``--quiet`` flag (spec §5.3.1) mutes human-readable
        chatter on the console without affecting the logger level or the
        file handlers. The handlers themselves implement the gate inside
        ``emit`` (see ``ConsoleHandler`` / ``TypingConsoleHandler``); this
        method exists so the orchestrator has a single named entry point
        rather than mutating handler attributes directly.

        Semantics:
          - ``set_quiet(True)`` suppresses INFO and DEBUG records on the
            console; WARNING and ERROR still surface so failure modes stay
            visible. File handlers (``activity.log``, ``error.log``) are
            unaffected — debug records under ``--debug --quiet`` still
            land in ``activity.log``.
          - ``set_quiet(False)`` restores the default behavior. Used by
            tests to leave the singleton clean between cases.

        Args:
            quiet: ``True`` to suppress informational console output,
                ``False`` to restore default behavior.
        """
        # Both handlers carry their own ``quiet`` attribute; flip them
        # together so callers don't have to know about the dual-handler
        # implementation detail.
        self.typing_console_handler.quiet = quiet
        self.console_handler.quiet = quiet

    def double_check(self, additional_text: str | None = None) -> None:
        if not additional_text:
            additional_text = (
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


logger = Logger()
