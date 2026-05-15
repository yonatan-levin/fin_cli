import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import IO, Any


class ConsoleHandler(logging.StreamHandler):
    """Plain-text console handler whose stream can be retargeted at runtime.

    Extends ``logging.StreamHandler`` so the parent already manages a
    ``stream`` attribute. We honor that attribute (defaulting to
    ``sys.stdout``) instead of using a bare ``print(...)`` so
    ``Logger.set_console_stream(...)`` can reroute the handler to stderr
    when ``--output -`` mode needs the stdout stream kept clean for CSV
    bytes (spec §5.2 + §5.3).
    """

    def __init__(self, stream: IO[str] | None = None) -> None:
        super().__init__(stream if stream is not None else sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        try:
            print(msg, file=self.stream)
        except Exception:
            self.handleError(record)


class TypingConsoleHandler(logging.StreamHandler):
    """Output stream to console using simulated typing.

    Honors the ``stream`` attribute inherited from ``logging.StreamHandler``
    so ``Logger.set_console_stream(...)`` can reroute the typing-effect
    chatter to stderr in stdout-streaming mode (spec §5.2 + §5.3).
    """

    def __init__(self, stream: IO[str] | None = None) -> None:
        super().__init__(stream if stream is not None else sys.stdout)

    def emit(self, record: logging.LogRecord) -> None:
        min_typing_speed = 0.05
        max_typing_speed = 0.01

        msg = self.format(record)
        try:
            words = msg.split()
            for i, word in enumerate(words):
                print(word, end="", flush=True, file=self.stream)
                if i < len(words) - 1:
                    print(" ", end="", flush=True, file=self.stream)
                typing_speed = random.uniform(min_typing_speed, max_typing_speed)
                time.sleep(typing_speed)
                # type faster after each word
                min_typing_speed = min_typing_speed * 0.95
                max_typing_speed = max_typing_speed * 0.95
            print(file=self.stream)
        except Exception:
            self.handleError(record)


class JsonFileHandler(logging.FileHandler):
    def __init__(
        self,
        filename: str | Path,
        mode: str = "a",
        encoding: str | None = None,
        delay: bool = False,
    ) -> None:
        super().__init__(filename, mode, encoding, delay)

    def emit(self, record: logging.LogRecord) -> None:
        json_data: Any = json.loads(self.format(record))
        with open(self.baseFilename, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
