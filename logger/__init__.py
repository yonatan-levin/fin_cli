"""Logger package — re-exports the Singleton plus its handlers and formatters.

Every name imported here is intentionally re-exported via ``__all__`` so
``from logger import logger`` (the canonical import per CLAUDE.md §Logging)
and the lower-level handler/formatter imports both work without triggering
ruff F401. Adding a new public re-export means appending to ``__all__``.
"""

from .formatters import AlgoFormatter, JsonFormatter, remove_color_codes
from .handlers import ConsoleHandler, JsonFileHandler, TypingConsoleHandler
from .log_cycle import (
    CURRENT_CONTEXT_FILE_NAME,
    FULL_MESSAGE_HISTORY_FILE_NAME,
    PROMPT_SUMMARY_FILE_NAME,
    SUMMARY_FILE_NAME,
    USER_INPUT_FILE_NAME,
    LogCycleHandler,
)
from .logger import Logger, logger

__all__ = [
    # Singleton instance + class (the canonical surface — see CLAUDE.md §Logging)
    "logger",
    "Logger",
    # Handlers (extend logging.{Stream,File}Handler; used by tests)
    "ConsoleHandler",
    "TypingConsoleHandler",
    "JsonFileHandler",
    # Formatters
    "AlgoFormatter",
    "JsonFormatter",
    "remove_color_codes",
    # Log-cycle plumbing
    "LogCycleHandler",
    "CURRENT_CONTEXT_FILE_NAME",
    "FULL_MESSAGE_HISTORY_FILE_NAME",
    "PROMPT_SUMMARY_FILE_NAME",
    "SUMMARY_FILE_NAME",
    "USER_INPUT_FILE_NAME",
]
