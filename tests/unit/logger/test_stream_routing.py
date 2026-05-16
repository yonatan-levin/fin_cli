"""Tests pinning the `Logger.set_console_stream` reroute.

Pillar 2 (`docs/features/archive/pipeline-mode-spec.md` §5.2 + §5.3) requires that
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


# ---------------------------------------------------------------------------
# Pillar 3 `--quiet` — `Logger.set_quiet` suppresses INFO/DEBUG on the
# console handlers while letting WARNING/ERROR through. File handlers are
# not exercised here (they have no quiet gate by design — debug records
# under `--debug --quiet` still need to land in `activity.log`).
# ---------------------------------------------------------------------------


def _make_record_with_level(level: int, message: str) -> logging.LogRecord:
    """Build a `LogRecord` at the given level with the AlgoFormatter extras.

    Mirrors `_make_record` above but with a configurable level so the
    quiet-gate tests can exercise WARNING/ERROR as well as INFO/DEBUG.
    """
    record = logging.LogRecord(
        name="LOGGER",
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )
    record.title = ""
    record.color = ""
    return record


def test_set_quiet_default_off_lets_info_through() -> None:
    """Default `quiet=False` keeps today's behavior: INFO records emit."""
    captured = io.StringIO()
    prior_stream = logger.console_handler.stream
    prior_quiet = logger.console_handler.quiet
    logger.set_console_stream(captured)
    try:
        # Confirm the default off-state actually holds at construction time;
        # if a previous test left the flag flipped on the singleton the test
        # below would pass for the wrong reason.
        logger.set_quiet(False)
        logger.console_handler.emit(_make_record_with_level(logging.INFO, "info-default"))
    finally:
        logger.set_console_stream(prior_stream)
        logger.console_handler.quiet = prior_quiet
        logger.typing_console_handler.quiet = prior_quiet

    assert "info-default" in captured.getvalue()


def test_set_quiet_true_suppresses_info_on_plain_handler() -> None:
    """`set_quiet(True)` short-circuits the plain handler at INFO level."""
    captured = io.StringIO()
    prior_stream = logger.console_handler.stream
    prior_quiet = logger.console_handler.quiet
    logger.set_console_stream(captured)
    try:
        logger.set_quiet(True)
        logger.console_handler.emit(_make_record_with_level(logging.INFO, "info-quiet"))
    finally:
        logger.set_console_stream(prior_stream)
        logger.set_quiet(prior_quiet)

    # The record should be suppressed entirely — the captured buffer stays
    # empty for an INFO emit under --quiet.
    assert "info-quiet" not in captured.getvalue()
    assert captured.getvalue() == ""


def test_set_quiet_true_suppresses_debug_on_plain_handler() -> None:
    """`set_quiet(True)` also suppresses DEBUG records.

    This is the `--debug --quiet` interaction guard: under --quiet, debug
    chatter on the console is unwanted even when --debug lowered the level.
    The file handlers still receive the record (verified by inspecting
    the orthogonal handler path; not asserted here to keep this unit test
    focused on the console handler).
    """
    captured = io.StringIO()
    prior_stream = logger.console_handler.stream
    prior_quiet = logger.console_handler.quiet
    logger.set_console_stream(captured)
    try:
        logger.set_quiet(True)
        logger.console_handler.emit(_make_record_with_level(logging.DEBUG, "debug-quiet"))
    finally:
        logger.set_console_stream(prior_stream)
        logger.set_quiet(prior_quiet)

    assert captured.getvalue() == ""


def test_set_quiet_true_still_emits_warning() -> None:
    """`--quiet` does not silence WARNINGs — failures must stay visible.

    Spec §5.3.1 row 1: "Errors and warnings still emitted." A pipeline that
    misconfigures `--quiet` and then hits a real failure mode must still see
    the warning on its stderr.
    """
    captured = io.StringIO()
    prior_stream = logger.console_handler.stream
    prior_quiet = logger.console_handler.quiet
    logger.set_console_stream(captured)
    try:
        logger.set_quiet(True)
        logger.console_handler.emit(_make_record_with_level(logging.WARNING, "warn-quiet"))
    finally:
        logger.set_console_stream(prior_stream)
        logger.set_quiet(prior_quiet)

    assert "warn-quiet" in captured.getvalue()


def test_set_quiet_true_still_emits_error() -> None:
    """`--quiet` does not silence ERRORs (companion to the WARNING test).

    Spec §7.4 row 6: `--debug --quiet` keeps debug-level messages routed
    normally; `--quiet` does not silence errors.
    """
    captured = io.StringIO()
    prior_stream = logger.console_handler.stream
    prior_quiet = logger.console_handler.quiet
    logger.set_console_stream(captured)
    try:
        logger.set_quiet(True)
        logger.console_handler.emit(_make_record_with_level(logging.ERROR, "err-quiet"))
    finally:
        logger.set_console_stream(prior_stream)
        logger.set_quiet(prior_quiet)

    assert "err-quiet" in captured.getvalue()


def test_set_quiet_toggles_both_handlers() -> None:
    """`set_quiet` flips the flag on **both** console handlers in one call.

    Callers don't have to know about the dual-handler implementation. Pin
    the contract so a future single-handler refactor or rename can't
    silently miss one side.
    """
    prior_plain = logger.console_handler.quiet
    prior_typing = logger.typing_console_handler.quiet
    try:
        logger.set_quiet(True)
        assert logger.console_handler.quiet is True
        assert logger.typing_console_handler.quiet is True
        logger.set_quiet(False)
        assert logger.console_handler.quiet is False
        assert logger.typing_console_handler.quiet is False
    finally:
        logger.console_handler.quiet = prior_plain
        logger.typing_console_handler.quiet = prior_typing


def test_set_quiet_true_suppresses_info_on_typing_handler() -> None:
    """`set_quiet(True)` short-circuits the typing-effect handler at INFO too.

    The typing handler runs an animated print loop; pinning the gate here
    guards against a refactor that only adds the check to the plain handler.
    """
    captured = io.StringIO()
    prior_stream = logger.typing_console_handler.stream
    prior_quiet = logger.typing_console_handler.quiet
    logger.set_console_stream(captured)
    try:
        logger.set_quiet(True)
        logger.typing_console_handler.emit(_make_record_with_level(logging.INFO, "typing-quiet"))
    finally:
        logger.set_console_stream(prior_stream)
        logger.set_quiet(prior_quiet)

    assert captured.getvalue() == ""
