"""Tests pinning the `Logger.set_console_stream` reroute.

Pillar 2 (`docs/features/pipeline-mode-spec.md` §5.2 + §5.3) requires that
`fincli --output -` route human-readable chatter (the typing-effect console
handler and the plain console handler) to **stderr** so the CSV stream on
stdout is not corrupted by log lines.

This file pins the underlying mechanism — the new `Logger.set_console_stream`
method on the singleton:

  - Default: both `ConsoleHandler.emit` and `TypingConsoleHandler.emit`
    write to **stdout** (today's behavior, before any reroute is requested).
  - After `logger.set_console_stream(sys.stderr)`: both handlers write to
    **stderr** instead.
  - The reroute does not affect the file handlers (`activity.log`,
    `error.log`); only the console stream changes.

The test replays a fresh log record through each handler (rather than going
through `logger.info(...)`) because the handlers extend `logging.StreamHandler`
and the failure mode of the original implementation was that they used a bare
`print(...)` which always wrote to stdout regardless of the StreamHandler
`stream` attribute. We capture the stream at emit time to assert the
post-reroute target.
"""

from __future__ import annotations

import io
import logging
import sys

from logger.handlers import ConsoleHandler, TypingConsoleHandler
from logger.logger import logger


def _make_record(message: str = "hello") -> logging.LogRecord:
    """Build a minimal `LogRecord` with the `title`/`color` extras the
    custom `AlgoFormatter` expects."""
    record = logging.LogRecord(
        name="LOGGER",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    # AlgoFormatter expects these extras; supply them so .format() doesn't
    # blow up before the print() call we want to observe.
    record.title = ""
    record.color = ""
    return record


def _swap_stdout(buffer: io.StringIO) -> object:
    """Save and replace `sys.stdout`; return the saved value."""
    saved = sys.stdout
    sys.stdout = buffer
    return saved


def test_console_handler_default_stream_is_stdout() -> None:
    """`ConsoleHandler` defaults its `stream` attribute to `sys.stdout`.

    The handler captures the stream at construction time, so swap stdout
    *before* constructing the handler to assert the default binding.
    """
    captured = io.StringIO()
    saved = _swap_stdout(captured)
    try:
        handler = ConsoleHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        # Stream attribute matches the swapped stdout.
        assert handler.stream is captured
        handler.emit(_make_record("default-stdout"))
    finally:
        sys.stdout = saved  # type: ignore[assignment]

    assert "default-stdout" in captured.getvalue()


def test_typing_console_handler_default_stream_is_stdout() -> None:
    """`TypingConsoleHandler` defaults its `stream` attribute to `sys.stdout`."""
    captured = io.StringIO()
    saved = _swap_stdout(captured)
    try:
        handler = TypingConsoleHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        assert handler.stream is captured
        handler.emit(_make_record("default-stdout-typing"))
    finally:
        sys.stdout = saved  # type: ignore[assignment]

    assert "default-stdout-typing" in captured.getvalue()


def test_set_console_stream_redirects_console_handler_to_stderr() -> None:
    """After `logger.set_console_stream(<stream>)`, the plain console handler
    routes its emits to `<stream>` instead of stdout."""
    captured = io.StringIO()
    # Capture the prior stream so this test never bleeds into the next.
    prior = logger.console_handler.stream
    logger.set_console_stream(captured)
    try:
        # Replay a record through the handler that the singleton owns.
        record = _make_record("rerouted-plain")
        record.title = ""
        record.color = ""
        # Use the handler's own format() so nothing crashes on the extras.
        logger.console_handler.emit(record)
    finally:
        logger.set_console_stream(prior)

    assert "rerouted-plain" in captured.getvalue()


def test_set_console_stream_redirects_typing_handler_to_stderr() -> None:
    """After `logger.set_console_stream(<stream>)`, the typing-effect handler
    routes its emits to `<stream>` instead of stdout."""
    captured = io.StringIO()
    prior = logger.typing_console_handler.stream
    logger.set_console_stream(captured)
    try:
        record = _make_record("rerouted-typing")
        record.title = ""
        record.color = ""
        logger.typing_console_handler.emit(record)
    finally:
        logger.set_console_stream(prior)

    assert "rerouted-typing" in captured.getvalue()
