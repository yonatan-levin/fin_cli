"""Click-surface tests for Pillar 2 deterministic output destination.

Pins the contract from `docs/features/pipeline-mode-spec.md` §5.2 + §7.3:

  - Two new options exist on `run_main`: `--output PATH` and its `-o` alias.
  - Both appear in `--help` output.
  - The flag forwards as `output_path=<value>` to `run_stock_screener`.
  - `--output -` (the stdout sentinel) is accepted verbatim.
  - The new flag is orthogonal to all input-mode flags — `--output` does not
    join the mutual-exclusion set; it composes with any input mode.
  - Back-compat: omitting `--output` forwards `output_path=""`.

Tests mock `fincli.app.main.run_stock_screener` so no HTTP fetch fires.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fincli.app.cli import run_main


@pytest.fixture
def mock_runner() -> Iterator[MagicMock]:
    """Patch out `run_stock_screener` so the test exercises CLI parsing only.

    Mirrors the fixture in `test_cli_pipeline.py`. The patch target is the
    import site (`fincli.app.main.run_stock_screener`) because `run_main`
    does a deferred import inside the function body.
    """
    with patch("fincli.app.main.run_stock_screener") as mock:
        yield mock


# ---------------------------------------------------------------------------
# Option presence — `--output` and `-o` surface in --help.
# ---------------------------------------------------------------------------


def test_output_option_in_help() -> None:
    """`--output` appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--output" in result.output


def test_output_short_alias_in_help() -> None:
    """`-o` short alias appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "-o" in result.output


# ---------------------------------------------------------------------------
# Threading — value forwards as `output_path` kwarg to `run_stock_screener`.
# ---------------------------------------------------------------------------


def test_output_long_form_threads_value(mock_runner: MagicMock) -> None:
    """`--output ./out.csv` forwards as `output_path="./out.csv"`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--output", "./out.csv"])
    assert result.exit_code == 0, result.output

    mock_runner.assert_called_once()
    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("output_path") == "./out.csv"


def test_output_short_form_threads_value(mock_runner: MagicMock) -> None:
    """`-o ./out.csv` forwards as `output_path="./out.csv"`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["-o", "./out.csv"])
    assert result.exit_code == 0, result.output

    mock_runner.assert_called_once()
    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("output_path") == "./out.csv"


def test_output_dash_sentinel_threads_through(mock_runner: MagicMock) -> None:
    """`--output -` forwards the literal `-` sentinel without modification.

    The dispatch decision (file vs stdout) lives inside `run_stock_screener`
    so the CLI layer just passes the value verbatim.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--output", "-"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("output_path") == "-"


def test_no_output_flag_threads_empty_string(mock_runner: MagicMock) -> None:
    """Omitting `--output` forwards `output_path=""` (back-compat default)."""
    runner = CliRunner()
    result = runner.invoke(run_main, [])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("output_path", "") == ""


# ---------------------------------------------------------------------------
# Composition — `--output` is orthogonal to input-mode flags.
# ---------------------------------------------------------------------------


def test_output_composes_with_filter_flag(mock_runner: MagicMock) -> None:
    """`--filter ... --output PATH` is a valid combination (no mutex error)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "fa_pe=u20", "--output", "./out.csv"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("output_path") == "./out.csv"
    # Filter still threaded.
    assert kwargs.get("filters")  # non-empty JSON


def test_output_composes_with_history_flag(mock_runner: MagicMock) -> None:
    """`--history --output PATH` is a valid combination."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--history", "--output", "./out.csv"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("history") is True
    assert kwargs.get("output_path") == "./out.csv"


def test_output_composes_with_scrape_link_flag(mock_runner: MagicMock) -> None:
    """`--scrape-link <url> --output PATH` is a valid combination."""
    url = "https://finviz.com/screener.ashx?v=111&f=foo"
    runner = CliRunner()
    result = runner.invoke(run_main, ["--scrape-link", url, "--output", "./out.csv"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("scrape_link") == url
    assert kwargs.get("output_path") == "./out.csv"


# ---------------------------------------------------------------------------
# Stdout cleanliness — `--output -` end-to-end (VERIFIER round-2 follow-up).
#
# Spec §7.3 bullet 5 ("emits no other bytes on stdout"). The earlier
# Interpretation-B logger reroute caught logger-bound chatter, but two
# `click.echo(...)` sites still wrote directly to stdout:
#   - cli.py:163 welcome banner
#   - quary_builders.py:28 "Base Url:" line
# These tests pin the fix end-to-end by mocking `fetch_page_sync` (so no HTTP
# fires) and asserting that captured stdout starts with the CSV header and
# contains none of the previously-leaked banner / URL / NA tokens.
# ---------------------------------------------------------------------------


# Minimal canned Finviz-screener HTML. Shape verified against
# `StockTableScreeningContent` + `StockTableScreenerParser` (one row, no
# pagination wrapper -> page_count returns 0 so `fetch_urls` runs the single
# page mock once). Column order matches `StockTableLocators.PD_TABLE_COLUMNS`.
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


def test_output_dash_stdout_is_csv_only() -> None:
    """`--output -` produces a stdout stream that contains only CSV bytes.

    Asserts:
      - exit code 0,
      - stdout starts with the canonical CSV header line,
      - stdout contains the parsed ticker symbol (sanity check that the
        pipeline actually ran),
      - stdout contains *none* of the previously-leaked tokens
        (`Welcome`, `Base Url:`, `<NA>`).

    Click 8.2 separates stdout / stderr on `Result` by default, so we can
    assert against `result.stdout` in isolation.
    """
    runner = CliRunner()
    # Patch the import site used inside `fincli.app.main` (the screener
    # orchestrator), not the source module — the deferred-import pattern in
    # `run_main` resolves the symbol at call time from `fincli.app.main`.
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    stdout = result.stdout
    # CSV header is written first by `pandas.DataFrame.to_csv` with
    # `index=False`; columns come from `StockTableLocators.PD_TABLE_COLUMNS`
    # (minus `Link`, plus `Symbol` appended by `build_data_frame`).
    assert stdout.startswith("No.,Ticker,"), (
        f"Expected stdout to start with CSV header; got first line: "
        f"{stdout.splitlines()[0] if stdout else '<empty>'!r}"
    )
    # Sanity: the row from the canned HTML actually flowed through.
    assert "AAPL" in stdout

    # Contract violations the fix is meant to prevent.
    assert "Welcome" not in stdout, "welcome banner leaked into stdout"
    assert "Base Url:" not in stdout, '"Base Url:" leaked into stdout'
    assert "<NA>" not in stdout, "pandas NA literal leaked into stdout"


def test_output_dash_banner_suppressed_not_rerouted() -> None:
    """The welcome banner is *suppressed* in `--output -` mode, not just routed.

    A banner on stderr is still noise for a pipeline consumer (`fincli
    --output - | jq` does not care about the welcome message). Pillar 5's
    `--quiet` will be the all-modes suppression channel; for `--output -`
    specifically we drop the banner outright.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync", return_value=_CANNED_FINVIZ_HTML):
        result = runner.invoke(
            run_main,
            ["--filter", "fa_pe=u20", "--output", "-"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    # Neither stream may carry the banner in stdout-streaming mode.
    assert "Welcome to the Stock Screener CLI!" not in result.stdout
    assert "Welcome to the Stock Screener CLI!" not in result.stderr


def test_output_default_mode_still_emits_banner(mock_runner: MagicMock) -> None:
    """Regression guard: the suppression is gated on `--output -` only.

    A bare `python -m fincli` invocation (or any non-stdout output mode) must
    still print the welcome banner to stdout — the suppression must not
    silently extend to interactive mode.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, [])
    assert result.exit_code == 0, result.output
    assert "Welcome to the Stock Screener CLI!" in result.output
