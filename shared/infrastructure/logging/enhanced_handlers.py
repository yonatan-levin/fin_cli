"""
Enhanced handlers for the shared logging system.

This module provides handlers that combine the structured logging capabilities
with legacy features like typing simulation and specialized file handling.
"""
import json
import logging
import random
import time
from pathlib import Path
from typing import Union


class EnhancedConsoleHandler(logging.StreamHandler):
    """Enhanced console handler with optional typing simulation."""

    def __init__(self, enable_typing: bool = False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.enable_typing = enable_typing

    def emit(self, record: logging.LogRecord) -> None:
        if self.enable_typing:
            self._emit_with_typing(record)
        else:
            self._emit_normal(record)

    def _emit_normal(self, record: logging.LogRecord) -> None:
        """Standard console output without typing simulation."""
        msg = self.format(record)
        try:
            print(msg)
        except Exception:
            self.handleError(record)

    def _emit_with_typing(self, record: logging.LogRecord) -> None:
        """Console output with typing simulation."""
        min_typing_speed = 0.05
        max_typing_speed = 0.01

        msg = self.format(record)
        try:
            words = msg.split()
            for i, word in enumerate(words):
                print(word, end="", flush=True)
                if i < len(words) - 1:
                    print(" ", end="", flush=True)
                typing_speed = random.uniform(
                    min_typing_speed, max_typing_speed)
                time.sleep(typing_speed)
                # type faster after each word
                min_typing_speed = min_typing_speed * 0.95
                max_typing_speed = max_typing_speed * 0.95
            print()
        except Exception:
            self.handleError(record)


class EnhancedJsonFileHandler(logging.FileHandler):
    """Enhanced JSON file handler with structured logging support."""

    def __init__(self, filename: Union[str, Path], mode="a", encoding=None, delay=False):
        super().__init__(filename, mode, encoding, delay)

    def emit(self, record: logging.LogRecord):
        try:
            formatted_message = self.format(record)
            # Try to parse as JSON first
            try:
                json_data = json.loads(formatted_message)
            except json.JSONDecodeError:
                # If not JSON, create a JSON structure
                json_data = {
                    "timestamp": record.created,
                    "level": record.levelname,
                    "message": formatted_message,
                    "name": record.name
                }

            with open(self.baseFilename, "w", encoding="utf-8") as f:
                json.dump(json_data, f, ensure_ascii=False, indent=4)
        except Exception:
            self.handleError(record)


class StructuredFileHandler(logging.FileHandler):
    """File handler optimized for structured logging with context preservation."""

    def __init__(self, filename: Union[str, Path], mode="a", encoding="utf-8", delay=False):
        super().__init__(filename, mode, encoding, delay)

    def emit(self, record: logging.LogRecord):
        try:
            # Format the record and write to file
            msg = self.format(record)
            if not msg.endswith('\n'):
                msg += '\n'

            with open(self.baseFilename, 'a', encoding='utf-8') as f:
                f.write(msg)
        except Exception:
            self.handleError(record)
