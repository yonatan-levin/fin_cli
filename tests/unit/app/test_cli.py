"""Regression tests for the `fincli.app.cli:run_main` Click entry point.

These tests pin today's CLI option-parsing surface so the upcoming pipeline-mode
refactor (docs/features/archive/pipeline-mode-spec.md, Tasks 3+) cannot silently drop
or alter any existing flag. They are deliberately option-shape tests only; they
do **not** execute the screener pipeline (that would hit Finviz over HTTP).

The `--scrape-link` option was incidentally lost once already in commit a840a1c
(2026-05-05) when the `fundainsight/` package was deleted; this file is the
back-compat seed that prevents a repeat across the broader refactor.
"""

from click.testing import CliRunner

from fincli.app.cli import run_main


def test_scrape_link_option_accepted() -> None:
    """`--scrape-link=<url>` must be a recognized option and appear in --help.

    Using --help short-circuits the actual screener pipeline so the test does not
    perform a real Finviz HTTP fetch.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--scrape-link=https://finviz.com/test", "--help"])
    assert result.exit_code == 0
    assert "--scrape-link" in result.output


def test_scrape_link_and_history_mutually_exclusive() -> None:
    """Passing both `--history` and `--scrape-link` must raise a UsageError.

    These are alternative input modes; combining them is undefined behavior, so
    the CLI rejects the combination at the parsing boundary.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--history", "--scrape-link=https://finviz.com/test"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_help_with_no_flags_exits_clean() -> None:
    """`fincli --help` must exit 0 and list every currently-supported flag.

    Pins today's option set so any future change that drops or renames an option
    will fail this test loudly.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    # Every option present today must appear in --help output.
    for option in ("--history", "--hist", "--debug", "--scrape-link"):
        assert option in result.output, f"Missing option in --help: {option}"


def test_history_flag_parses() -> None:
    """`fincli --history --help` must parse without error.

    Pairing the flag with `--help` lets us verify Click accepts the option
    without actually running `run_stock_screener` (which would attempt to read
    `<history_dir>/filter_history.json` and then hit Finviz).
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--history", "--help"])
    assert result.exit_code == 0
    assert "--history" in result.output


def test_history_alias_parses() -> None:
    """`--hist` is an alias for `--history` and must continue to parse."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--hist", "--help"])
    assert result.exit_code == 0


def test_debug_flag_parses() -> None:
    """`fincli --debug --help` must parse without error."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--debug", "--help"])
    assert result.exit_code == 0
    assert "--debug" in result.output
