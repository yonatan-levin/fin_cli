"""End-to-end zero-row success tests (Pillar 4 — spec §5.4 last two bullets).

Pins the "every successful run produces a discoverable output" contract:
even when Finviz returns zero matching tickers, the orchestrator writes
(or streams) a header-only CSV and exits 0. Closes Task-5 QA MEDIUM #2
(the empty ``OUTPUT_PATH=`` value on the zero-row branch).

Acceptance bullets from spec §7.5:

  * Zero-row result -> exit 0, CSV header row only, no data rows.
  * ``--output -`` zero-row -> stdout contains header line + nothing else.
  * ``--output PATH`` zero-row -> file exists with header + nothing else,
    ``OUTPUT_PATH=<abs>`` populated (not the bug-state empty value).
  * ``--json-summary`` reports ``row_count: 0`` and ``exit_code: 0``.

The mocked fetch returns the ``finviz_empty.html`` fixture so the
``aggregate_rows`` step returns an empty list and the orchestrator routes
to its zero-row branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from _fixtures_loader import finviz_empty_html
from click.testing import CliRunner

from fincli.app.cli import run_main
from fincli.app.main import OUTPUT_PATH_LINE_PREFIX
from fincli.stock_screening.locators.stock_table_locators import StockTableLocators

# Expected CSV header line — Finviz locator columns minus ``Link`` plus
# ``Symbol`` appended last. Pinned here so any future column-order change
# fails this regression test loudly. Spec §5.6 + CONTRACTS §3.1.
_EXPECTED_HEADER = ",".join(
    [col for col in StockTableLocators.PD_TABLE_COLUMNS if col != "Link"] + ["Symbol"]
)

_CANNED_EMPTY_HTML = finviz_empty_html()


# ---------------------------------------------------------------------------
# `--output PATH` zero-row — file written with header only; exit 0;
# OUTPUT_PATH= populated (not empty).
# ---------------------------------------------------------------------------


def test_zero_row_with_file_output_writes_header_only_csv(tmp_path: Path) -> None:
    """`--output PATH` on a zero-row run writes the header line + zero data rows.

    Pins §5.4 ("header-only CSV") + §7.5 bullet 2 + the §5.4 closure of the
    Task-5 QA MEDIUM #2 empty-OUTPUT_PATH bug.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_EMPTY_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    # Zero rows is success, not failure (Pillar 4 spec — §5.4).
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert target.exists(), "Zero-row run must still write a header-only CSV"

    # File contains exactly the header line; no data rows.
    contents = target.read_text(encoding="utf-8").splitlines()
    # Pandas writes one header line + one trailing newline; splitlines drops
    # the trailing newline, leaving exactly one entry.
    assert contents == [_EXPECTED_HEADER], (
        f"Expected header-only CSV; got {len(contents)} lines: {contents!r}"
    )


def test_zero_row_with_file_output_path_label_is_absolute(tmp_path: Path) -> None:
    """OUTPUT_PATH=<abs> on a zero-row run is the resolved absolute path.

    Pins the Task-5 QA MEDIUM #2 closure: previously the zero-row branch
    returned silently before resolving the destination, leaving the
    discovery line as ``OUTPUT_PATH=`` (empty value). The header-only
    write resolves and writes the path, so ``_resolve_output_path_label``
    returns the absolute string.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_EMPTY_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    expected_label = f"{OUTPUT_PATH_LINE_PREFIX}{target.resolve()}"
    assert expected_label in result.stderr, (
        f"Expected stderr to contain {expected_label!r}; got: {result.stderr!r}"
    )
    # And specifically NOT the bug-state empty value.
    assert f"{OUTPUT_PATH_LINE_PREFIX}\n" not in result.stderr, (
        "Regression: OUTPUT_PATH= must not be empty on the zero-row success path"
    )


# ---------------------------------------------------------------------------
# `--output -` zero-row — stdout streams header only; stderr carries
# OUTPUT_PATH=-.
# ---------------------------------------------------------------------------


def test_zero_row_with_stdout_streaming_writes_header_only(tmp_path: Path) -> None:
    """`--output -` zero-row run streams the header line + zero data rows."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_EMPTY_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    stdout_lines = result.stdout.splitlines()
    assert stdout_lines == [_EXPECTED_HEADER], (
        f"Expected stdout to contain only the CSV header; got {len(stdout_lines)} "
        f"lines: {stdout_lines!r}"
    )

    # OUTPUT_PATH=- still emitted on stderr.
    assert f"{OUTPUT_PATH_LINE_PREFIX}-" in result.stderr


# ---------------------------------------------------------------------------
# `--json-summary` zero-row — row_count == 0, exit_code == 0.
# ---------------------------------------------------------------------------


def _extract_summary(stream: str) -> dict:
    for line in reversed(stream.splitlines()):
        stripped = line.strip()
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"No JSON summary line found in stream: {stream!r}")


def test_zero_row_summary_reports_zero_row_count(tmp_path: Path) -> None:
    """The JSON summary on a zero-row run has ``row_count: 0``."""
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_EMPTY_HTML):
        result = runner.invoke(
            run_main,
            [
                "--filter",
                "fa_pe=u20",
                "--quiet",
                "--output",
                str(target),
                "--json-summary",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    summary = _extract_summary(result.stdout)
    assert summary["row_count"] == 0
    assert summary["exit_code"] == 0  # zero-row is success, not failure
    # And `output_path` is the resolved absolute path (not empty).
    assert summary["output_path"] == str(target.resolve())


def test_zero_row_summary_stdout_streaming_lands_on_stderr() -> None:
    """`--output - --json-summary` on a zero-row run -> summary on stderr."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_EMPTY_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-", "--json-summary"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    summary = _extract_summary(result.stderr)
    assert summary["row_count"] == 0
    assert summary["exit_code"] == 0
    assert summary["output_path"] == "-"


# ---------------------------------------------------------------------------
# Stdout cleanliness regression: even on the zero-row path, no banner or
# log lines leak into stdout under `--output -`.
# ---------------------------------------------------------------------------


def test_zero_row_stdout_streaming_no_banner_or_logs() -> None:
    """`--output -` zero-row run keeps stdout free of banner / log lines."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_EMPTY_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    # Stdout is exactly the header line — confirm the boundary explicitly.
    assert "Welcome" not in result.stdout
    assert "Fetching HTML" not in result.stdout
    assert "Data Handling" not in result.stdout
    assert OUTPUT_PATH_LINE_PREFIX not in result.stdout
