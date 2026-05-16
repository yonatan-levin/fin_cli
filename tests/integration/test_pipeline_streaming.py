"""End-to-end stream discipline tests (Pillar 3 — `docs/features/archive/pipeline-mode-spec.md`).

These tests drive the full Click entry point (`run_main`) with `CliRunner`,
mock out the network layer at `fincli.app.main.fetch_page_sync`, and assert
on the post-run stdout / stderr contents to pin the §7.4 acceptance bullets:

  - `fincli --output - ...` produces a CSV on stdout with no log lines and
    no banner. (The `=HYPERLINK(...)` strip is Task 6 — this file deliberately
    does *not* assert on it for §7.4 bullet 1; only the no-banner / no-log-lines
    half of that bullet is verified here.)
  - In the same invocation, stderr contains progress lines and an
    `OUTPUT_PATH=-` line as the **last** line on stderr.
  - `--quiet` suppresses the welcome banner and progress lines on stdout
    without changing the output destination.
  - `--quiet --output PATH` still suppresses chatter but writes to PATH.

Click 8.2 separates `result.stdout` from `result.stderr` on the `Result`
object so the assertions can target the streams independently. The
`fetch_page_sync` patch target is `fincli.app.main.fetch_page_sync` —
matching the import inside the orchestrator (the deferred-import pattern
in `run_main` resolves the symbol at call time from the orchestrator
module, not from the source).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fincli.app.cli import run_main
from fincli.app.main import OUTPUT_PATH_LINE_PREFIX

from _fixtures_loader import finviz_happy_html

# Canned one-row screener HTML lives under ``tests/integration/fixtures/``;
# the loader is the single source of truth so all three integration test
# files share the exact same payload (REVIEWER follow-up from Task 5).
_CANNED_FINVIZ_HTML = finviz_happy_html()


# ---------------------------------------------------------------------------
# `--output -` — stream discipline. Stdout pure CSV; stderr carries progress
# plus a trailing `OUTPUT_PATH=-` line.
# ---------------------------------------------------------------------------


def test_output_dash_stdout_has_no_log_lines_or_banner() -> None:
    """`--output -` keeps stdout free of any log line or banner.

    Pins §7.4 bullet 1, partial: no log lines + no banner. The
    `=HYPERLINK(...)` strip half of bullet 1 is Task 6 and is intentionally
    not asserted here.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    # CSV header first — pandas `to_csv(index=False)` writes the column
    # names then the data row(s). Nothing else is allowed before it.
    stdout = result.stdout
    assert stdout.startswith("No.,Ticker,"), (
        f"Expected stdout to start with CSV header; "
        f"got first line: {stdout.splitlines()[0] if stdout else '<empty>'!r}"
    )
    # No banner; no logger-emitted strings on stdout. The welcome banner
    # is suppressed entirely in `--output -` mode, not just rerouted.
    assert "Welcome to the Stock Screener CLI!" not in stdout
    assert "Fetching HTML" not in stdout
    assert "Data Handling" not in stdout
    # No `OUTPUT_PATH=` line on stdout — that's a stderr-only signal.
    assert OUTPUT_PATH_LINE_PREFIX not in stdout


def test_output_dash_stderr_has_progress_and_output_path_line() -> None:
    """Stderr carries progress lines + a trailing `OUTPUT_PATH=-` line.

    Pins §7.4 bullet 2. Also pins that `OUTPUT_PATH=-` is the **last** line
    on stderr (the chokepoint emission order rule from spec §5.3).
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stdout: {result.stdout}"

    stderr = result.stderr
    # Some progress chatter from the orchestrator reached stderr.
    assert "Fetching HTML" in stderr or "Data Handling" in stderr

    # OUTPUT_PATH=- is the last non-empty line on stderr.
    non_empty_lines = [line for line in stderr.splitlines() if line.strip()]
    assert non_empty_lines, "stderr was empty; expected at least the OUTPUT_PATH line"
    last_line = non_empty_lines[-1]
    assert last_line == f"{OUTPUT_PATH_LINE_PREFIX}-", (
        f"Expected last stderr line to be '{OUTPUT_PATH_LINE_PREFIX}-'; got {last_line!r}"
    )


def test_output_dash_output_path_line_emitted_exactly_once() -> None:
    """The `OUTPUT_PATH=` line lands on stderr exactly once."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    occurrences = result.stderr.count(OUTPUT_PATH_LINE_PREFIX)
    assert occurrences == 1, (
        f"Expected exactly one `{OUTPUT_PATH_LINE_PREFIX}` line; got {occurrences}"
    )


# ---------------------------------------------------------------------------
# `--output PATH` — `OUTPUT_PATH=<abspath>` lands on stderr, file is written.
# ---------------------------------------------------------------------------


def test_output_path_emits_absolute_path_on_stderr(tmp_path: Path) -> None:
    """`--output PATH` writes the resolved absolute path after `OUTPUT_PATH=`.

    A pipeline that prefers `tail -n1 stderr | cut -d= -f2-` over the JSON
    summary must get back a path it can `cat` without further normalization.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert target.exists(), "CSV file was not written to --output PATH"

    expected_label = f"{OUTPUT_PATH_LINE_PREFIX}{target.resolve()}"
    assert expected_label in result.stderr, (
        f"Expected stderr to contain {expected_label!r}; got: {result.stderr!r}"
    )

    # Last non-empty line is still OUTPUT_PATH=... (no JSON summary appended
    # when --json-summary is absent).
    non_empty_lines = [line for line in result.stderr.splitlines() if line.strip()]
    assert non_empty_lines
    assert non_empty_lines[-1].startswith(OUTPUT_PATH_LINE_PREFIX)


# ---------------------------------------------------------------------------
# `--quiet` — suppresses welcome banner and progress on stdout. Stderr's
# OUTPUT_PATH line still emits (pipelines need it even in quiet mode).
# ---------------------------------------------------------------------------


def test_quiet_suppresses_banner_on_stdout(tmp_path: Path) -> None:
    """`--quiet` drops the welcome banner from stdout.

    Pins §7.4 bullet 5: `--quiet` suppresses the welcome banner and progress
    lines on stdout but does not change the output destination.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--quiet", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert target.exists(), "File destination must still receive the CSV under --quiet"

    # No welcome banner on stdout.
    assert "Welcome to the Stock Screener CLI!" not in result.stdout
    # Progress lines (INFO-level) suppressed by the handler quiet gate.
    # Note: progress lines go through the typing console handler which
    # writes to stdout by default; under --quiet they should be muted.
    assert "Fetching HTML" not in result.stdout
    assert "Data Handling" not in result.stdout


def test_quiet_preserves_output_path_line_on_stderr(tmp_path: Path) -> None:
    """`--quiet` does NOT suppress the `OUTPUT_PATH=` line — pipelines need it.

    Spec §5.3.3 + the brief's tricky-bit #3: independent of `--quiet`.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--quiet", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    expected_label = f"{OUTPUT_PATH_LINE_PREFIX}{target.resolve()}"
    assert expected_label in result.stderr
