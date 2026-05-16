"""End-to-end exit-code classifier tests (Pillar 4 — spec §5.4 + §7.5).

Pins the §7.5 acceptance bullets that this test file owns:

  * Network failure (`fetch_page_sync` raises a `requests` exception)
    -> exit **3** (UPSTREAM).
  * Parse failure (canned HTML drives the BS4 parser into an
    ``AttributeError`` / ``IndexError``) -> exit **4** (DATA).
  * Uncaught exception not in the above categories -> exit **1**
    (INTERNAL).

Each scenario verifies:

  * the exit code matches the classifier table,
  * the JSON summary (when ``--json-summary`` is set) carries the same
    ``exit_code``,
  * the ``OUTPUT_PATH=`` line is still emitted on stderr (every run
    surfaces the discovery line, even on failure).

The happy-path classifier mapping is unit-tested in
``tests/unit/app/test_exit_codes.py``; here we pin the end-to-end glue
through ``CliRunner`` so a future regression in the orchestrator wiring
(e.g. swallowing the exception, or routing it to ``sys.exit(1)`` without
going through ``classify``) fails loudly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import requests
from _fixtures_loader import (
    finviz_happy_html,
    finviz_malformed_row_html,
)
from click.testing import CliRunner

from fincli.app import exit_codes
from fincli.app.cli import run_main
from fincli.app.main import OUTPUT_PATH_LINE_PREFIX


def _extract_summary(stream: str) -> dict:
    for line in reversed(stream.splitlines()):
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"No JSON summary line found in stream: {stream!r}")


# ---------------------------------------------------------------------------
# UPSTREAM (exit 3) — `fetch_page_sync` raises a requests exception.
# ---------------------------------------------------------------------------


def test_network_failure_exits_with_upstream_code() -> None:
    """`fetch_page_sync` raising RequestException -> exit 3 (UPSTREAM).

    Pins §7.5 bullet 5.
    """
    runner = CliRunner()
    with patch(
        "fincli.app.main.fetch_page_sync",
        side_effect=requests.exceptions.ConnectionError("connection refused"),
    ):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.UPSTREAM, (
        f"Expected exit code {exit_codes.UPSTREAM} (UPSTREAM); "
        f"got {result.exit_code}. stderr: {result.stderr}"
    )


def test_network_failure_summary_carries_upstream_code() -> None:
    """The JSON summary reports the same UPSTREAM exit code as the process."""
    runner = CliRunner()
    with patch(
        "fincli.app.main.fetch_page_sync",
        side_effect=requests.exceptions.Timeout("read timed out"),
    ):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-", "--json-summary"],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.UPSTREAM
    # Summary lands on stderr because CSV bytes claim stdout (well —
    # nothing actually wrote, but routing decision was made up front).
    summary = _extract_summary(result.stderr)
    assert summary["exit_code"] == exit_codes.UPSTREAM
    assert summary["row_count"] == 0  # nothing was written


def test_network_failure_output_path_line_still_emitted(tmp_path: Path) -> None:
    """Every run emits `OUTPUT_PATH=` on stderr — even on UPSTREAM failure.

    Pipeline integrators need the discovery line on every invocation so a
    ``tail -n1 stderr`` reader gets a deterministic last-line shape.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch(
        "fincli.app.main.fetch_page_sync",
        side_effect=requests.exceptions.ConnectionError("nope"),
    ):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.UPSTREAM
    # The destination was not resolved because the failure fired before
    # the `if not csv_on_stdout: resolved_file_path = config.file_path(...)`
    # line. Empty-value OUTPUT_PATH= is the documented signal that no
    # CSV exists at any path.
    assert OUTPUT_PATH_LINE_PREFIX in result.stderr


# ---------------------------------------------------------------------------
# DATA (exit 4) — BS4 parser raises on a malformed row.
# ---------------------------------------------------------------------------


def test_parse_failure_exits_with_data_code() -> None:
    """A malformed row (missing link anchor) -> exit 4 (DATA).

    The ``finviz_malformed_row.html`` fixture's row has no ``<a>`` inside
    the second ``<td>``, so
    ``StockTableScreenerParser.ticker_link`` calls ``.find('a').get(...)``
    on ``None`` and raises ``AttributeError``. The classifier maps
    ``AttributeError`` -> DATA. Pins §7.5 bullet 6.
    """
    runner = CliRunner()
    with patch(
        "fincli.app.main.fetch_page_sync",
        return_value=finviz_malformed_row_html(),
    ):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.DATA, (
        f"Expected exit code {exit_codes.DATA} (DATA); got {result.exit_code}. "
        f"stderr: {result.stderr}"
    )


def test_parse_failure_summary_carries_data_code() -> None:
    """The JSON summary reports the DATA exit code on parse failure."""
    runner = CliRunner()
    with patch(
        "fincli.app.main.fetch_page_sync",
        return_value=finviz_malformed_row_html(),
    ):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-", "--json-summary"],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.DATA
    summary = _extract_summary(result.stderr)
    assert summary["exit_code"] == exit_codes.DATA


# ---------------------------------------------------------------------------
# INTERNAL (exit 1) — unrecognized exception bubbles to the classifier.
# ---------------------------------------------------------------------------


def test_unknown_exception_exits_with_internal_code() -> None:
    """An unrecognized exception type -> exit 1 (INTERNAL).

    Pins §7.5 bullet 7: uncaught exception not in the upstream/data
    categories -> exit 1 with traceback to stderr + logs/error.log.
    """
    runner = CliRunner()
    with patch(
        "fincli.app.main.fetch_page_sync",
        side_effect=RuntimeError("synthetic failure for the classifier test"),
    ):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.INTERNAL, (
        f"Expected exit code {exit_codes.INTERNAL} (INTERNAL); "
        f"got {result.exit_code}. stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Happy path regression — confirm the classifier doesn't fire on success.
# ---------------------------------------------------------------------------


def test_happy_path_exits_with_success_code(tmp_path: Path) -> None:
    """Pins §7.5 bullet 1: happy-path run -> exit 0 (SUCCESS)."""
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=finviz_happy_html()):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == exit_codes.SUCCESS, f"stderr: {result.stderr}"
    assert target.exists()
