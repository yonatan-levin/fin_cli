"""Regression tests for the `--scrape-link` Click option on `fincli.app.cli:run_main`.

Background: the `--scrape-link` option was incidentally lost in commit a840a1c
(2026-05-05) when the `fundainsight/` package was deleted. These tests pin the
restored behavior so a future refactor cannot silently drop it again.
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
