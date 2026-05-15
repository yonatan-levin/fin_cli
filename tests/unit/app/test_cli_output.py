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
