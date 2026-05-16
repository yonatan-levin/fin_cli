"""End-to-end JSON summary tests (Pillar 3 — spec §5.3.4 + §7.4 bullets 3,4,7).

These tests drive `run_main` via `CliRunner` with `fetch_page_sync` mocked
and assert on the single-line JSON summary emitted at end of run:

  - `fincli --output ./out.csv --json-summary` prints exactly one JSON line
    on stdout; all progress on stderr.
  - `fincli --output - --json-summary` prints CSV bytes on stdout only and
    the JSON summary on stderr *after* `OUTPUT_PATH=-`.
  - The summary validates against the §5.3.4 schema with `schema_version: 1`.
  - All nine fields are present with their declared types.

The schema fields (per spec §5.3.4):

  schema_version: int (== 1)
  exit_code: int
  output_path: str   (absolute path or "-")
  row_count: int
  query_url: str
  filters: object | null
  started_at: str    (ISO-8601 UTC)
  finished_at: str
  duration_ms: int
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from fincli.app.cli import run_main
from fincli.app.main import (
    JSON_SUMMARY_SCHEMA_VERSION,
    OUTPUT_PATH_LINE_PREFIX,
)

# Reused canned HTML — one ticker row, no pagination wrapper. See
# `tests/integration/test_pipeline_streaming.py` for the rationale.
_CANNED_FINVIZ_HTML = b"""<html><body>
<table class="styled-table-new"><tbody>
<tr valign="top">
  <td>1</td>
  <td><a href="/quote.ashx?t=AAPL">AAPL</a></td>
  <td>Apple Inc.</td>
  <td>Technology</td>
  <td>Consumer Electronics</td>
  <td>USA</td>
  <td>2.89T</td>
  <td>28.52</td>
  <td>182.63</td>
  <td>-1.23%</td>
  <td>52,436,789</td>
</tr>
</tbody></table>
</body></html>"""


# Field set the §5.3.4 schema declares; pinned so a future field addition
# (non-breaking per the schema_version contract) doesn't silently slip past.
_REQUIRED_SUMMARY_FIELDS = {
    "schema_version",
    "exit_code",
    "output_path",
    "row_count",
    "query_url",
    "filters",
    "started_at",
    "finished_at",
    "duration_ms",
}


def _extract_json_line(stream: str) -> dict:
    """Find and parse the single-line JSON summary in `stream`.

    The summary is always on the *last* line of its target stream by
    contract; this helper deliberately walks from the bottom up rather than
    grabbing the last non-empty line so a trailing newline doesn't trip the
    parser.
    """
    for line in reversed(stream.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        # The summary line is valid JSON starting with `{`. Skip any
        # progress / `OUTPUT_PATH=` lines that aren't.
        if stripped.startswith("{"):
            return json.loads(stripped)
    raise AssertionError(f"No JSON summary line found in stream: {stream!r}")


# ---------------------------------------------------------------------------
# `--output PATH --json-summary` — summary on stdout, progress on stderr.
# ---------------------------------------------------------------------------


def test_summary_with_file_output_lands_on_stdout(tmp_path: Path) -> None:
    """`fincli --output ./out.csv --json-summary` prints the JSON on stdout.

    Pins §7.4 bullet 3.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            [
                "--filter",
                "fa_pe=u20",
                "--output",
                str(target),
                "--json-summary",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert target.exists(), "File destination must be written even with --json-summary"

    summary = _extract_json_line(result.stdout)
    assert summary["schema_version"] == JSON_SUMMARY_SCHEMA_VERSION
    assert set(summary.keys()) >= _REQUIRED_SUMMARY_FIELDS


def test_summary_with_file_output_exactly_one_json_line_on_stdout(tmp_path: Path) -> None:
    """Exactly one JSON-shaped line on stdout (no extra summary lines)."""
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            [
                "--filter",
                "fa_pe=u20",
                "--quiet",  # use --quiet so banner/progress don't muddy stdout
                "--output",
                str(target),
                "--json-summary",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    # Lines that parse as JSON objects.
    json_lines = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("{"):
            try:
                json_lines.append(json.loads(stripped))
            except json.JSONDecodeError:
                pass
    assert len(json_lines) == 1, (
        f"Expected exactly one JSON summary line on stdout; got {len(json_lines)}"
    )


def test_summary_with_file_output_progress_on_stderr(tmp_path: Path) -> None:
    """Pins that progress chatter stays off the summary stream (stdout)."""
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            [
                "--filter",
                "fa_pe=u20",
                "--output",
                str(target),
                "--json-summary",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    # `OUTPUT_PATH=...` always lands on stderr — confirms it didn't leak
    # onto stdout next to the JSON summary.
    assert OUTPUT_PATH_LINE_PREFIX in result.stderr
    assert OUTPUT_PATH_LINE_PREFIX not in result.stdout


# ---------------------------------------------------------------------------
# `--output - --json-summary` — CSV on stdout, summary on stderr (after OUTPUT_PATH=-).
# ---------------------------------------------------------------------------


def test_summary_with_stdout_streaming_lands_on_stderr() -> None:
    """`fincli --output - --json-summary` puts the summary on **stderr**.

    Pins §7.4 bullet 4: CSV on stdout, summary on stderr (after
    `OUTPUT_PATH=-`). The summary must NOT corrupt the CSV stream.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-", "--json-summary"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    # Stdout is pure CSV — no JSON line on stdout under --output -.
    assert "{" not in result.stdout or not any(
        line.strip().startswith("{") for line in result.stdout.splitlines()
    )

    # Summary lands on stderr.
    summary = _extract_json_line(result.stderr)
    assert summary["schema_version"] == JSON_SUMMARY_SCHEMA_VERSION
    assert summary["output_path"] == "-"


def test_summary_with_stdout_streaming_emits_after_output_path_line() -> None:
    """Ordering rule: on stderr, `OUTPUT_PATH=-` comes BEFORE the summary line.

    Pins spec §5.3 routing-table row 4 ordering ("OUTPUT_PATH=- + (if
    --json-summary) the summary"). A consumer that reads stderr line-by-line
    needs the discovery line first so it can branch on the destination
    before the heavier JSON payload arrives.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-", "--json-summary"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0

    lines = [line for line in result.stderr.splitlines() if line.strip()]
    # Locate the OUTPUT_PATH line and the JSON line by their distinctive
    # leading character (`O` vs `{`) and assert the indices.
    output_path_idx = next(
        i for i, line in enumerate(lines) if line.startswith(OUTPUT_PATH_LINE_PREFIX)
    )
    summary_idx = next(i for i, line in enumerate(lines) if line.lstrip().startswith("{"))
    assert output_path_idx < summary_idx, (
        f"Expected `OUTPUT_PATH=` (idx {output_path_idx}) to precede "
        f"summary (idx {summary_idx}); stderr was:\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Schema-level assertions — every §5.3.4 field present with the right shape.
# ---------------------------------------------------------------------------


def test_summary_schema_full_shape(tmp_path: Path) -> None:
    """Every §5.3.4 field present with the right Python type.

    Pins §7.4 bullet 7: the JSON summary validates against §5.3.4 schema
    with `schema_version: 1`.
    """
    target = tmp_path / "out.csv"
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
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
    summary = _extract_json_line(result.stdout)

    # All required fields present.
    assert set(summary.keys()) == _REQUIRED_SUMMARY_FIELDS

    # Type and value constraints, per the §5.3.4 schema table.
    assert isinstance(summary["schema_version"], int)
    assert summary["schema_version"] == 1

    assert isinstance(summary["exit_code"], int)
    assert summary["exit_code"] == 0

    assert isinstance(summary["output_path"], str)
    # File destination -> absolute path.
    assert summary["output_path"] == str(target.resolve())

    assert isinstance(summary["row_count"], int)
    assert summary["row_count"] == 1  # canned HTML has one row

    assert isinstance(summary["query_url"], str)
    assert summary["query_url"].startswith("https://finviz.com/screener.ashx")

    # `filters` is the resolved dict for the --filter path.
    assert isinstance(summary["filters"], dict)
    assert summary["filters"] == {"fa_pe": "u20"}

    # Timestamps parse as ISO-8601 with a tz suffix.
    started_at = datetime.fromisoformat(summary["started_at"])
    finished_at = datetime.fromisoformat(summary["finished_at"])
    assert started_at.tzinfo is not None
    assert finished_at.tzinfo is not None
    # Ordering invariant.
    assert finished_at >= started_at

    # Duration is a non-negative integer count of milliseconds.
    assert isinstance(summary["duration_ms"], int)
    assert summary["duration_ms"] >= 0


def test_summary_filters_is_null_for_scrape_link_path() -> None:
    """The `--scrape-link` path emits `filters: null` per §5.3.4 row 6.

    No filter resolution happens on the scrape-link path (URL is opaque),
    so the resolved-dict field is explicitly null rather than an empty
    object — pipeline consumers can branch on null to detect that mode.
    """
    runner = CliRunner()
    url = "https://finviz.com/screener.ashx?v=111&f=fa_pe_u20"
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            [
                "--scrape-link",
                url,
                "--output",
                "-",
                "--json-summary",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    summary = _extract_json_line(result.stderr)
    assert summary["filters"] is None
    # `query_url` is the supplied URL verbatim on the scrape-link path.
    assert summary["query_url"] == url


def test_summary_output_path_label_is_dash_under_stdout_streaming() -> None:
    """Under `--output -`, the summary's `output_path` field is `"-"`."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-", "--json-summary"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    summary = _extract_json_line(result.stderr)
    assert summary["output_path"] == "-"
