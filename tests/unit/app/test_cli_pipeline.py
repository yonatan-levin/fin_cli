"""Click-surface tests for Pillar 1 structured filter input.

Pins the contract from `docs/features/archive/pipeline-mode-spec.md` §5.1 + §6.2:

  - Three new options exist on `run_main`: `--filter`, `--filters-json`,
    `--filters-file`.
  - Mutual-exclusion across `{--filter, --filters-json, --filters-file,
    --history, --scrape-link}` raises a `click.UsageError` (exit 2) with the
    canonical message.
  - The CLI normalizes all three forms into a single JSON string and threads
    it through `run_stock_screener` -> `build_config(filters=...)`.
  - Malformed `--filter` tokens (missing `=`, empty key/value) raise a
    `click.UsageError` naming the offending token.
  - Unknown filter keys/values surface as exit 2 with a helpful message
    (validator chained via `build_config`).
  - Back-compat: today's options (`--history`, `--debug`, `--scrape-link`)
    still parse; the existing `tests/unit/app/test_cli.py` regression seed
    must keep passing.

Tests mock `fincli.app.main.run_stock_screener` so no HTTP fetch fires.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fincli.app.cli import run_main


@pytest.fixture
def mock_runner() -> Iterator[MagicMock]:
    """Patch out `run_stock_screener` so the test exercises CLI parsing only.

    The patch target lives in `fincli.app.cli` (the import site, since
    `run_main` does `from .main import run_stock_screener` at call time).
    Patching the source module wouldn't catch the import that has already
    happened inside `run_main`. We patch `fincli.app.main.run_stock_screener`
    which is read at the moment of the import statement.
    """
    with patch("fincli.app.main.run_stock_screener") as mock:
        yield mock


# ---------------------------------------------------------------------------
# Option presence — three new flags surface in --help.
# ---------------------------------------------------------------------------


def test_filter_option_in_help() -> None:
    """`--filter` appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--filter" in result.output


def test_filters_json_option_in_help() -> None:
    """`--filters-json` appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--filters-json" in result.output


def test_filters_file_option_in_help() -> None:
    """`--filters-file` appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--filters-file" in result.output


# ---------------------------------------------------------------------------
# Option parsing — valid invocations route into run_stock_screener with the
# normalized JSON string.
# ---------------------------------------------------------------------------


def test_filter_repeatable_normalized_to_json(mock_runner: MagicMock) -> None:
    """`--filter k=v --filter k2=v2` becomes a JSON dict string passed to
    `run_stock_screener(..., filters=<json>)`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "fa_pe=u20", "--filter", "sec=energy"])
    assert result.exit_code == 0, result.output

    mock_runner.assert_called_once()
    kwargs = mock_runner.call_args.kwargs
    assert "filters" in kwargs
    parsed = json.loads(kwargs["filters"])
    assert parsed == {"fa_pe": "u20", "sec": "energy"}


def test_filters_json_passed_through(mock_runner: MagicMock) -> None:
    """`--filters-json '<dict>'` forwards the literal string to the orchestrator."""
    runner = CliRunner()
    payload = '{"fa_pe":"u20"}'
    result = runner.invoke(run_main, ["--filters-json", payload])
    assert result.exit_code == 0, result.output

    mock_runner.assert_called_once()
    kwargs = mock_runner.call_args.kwargs
    parsed = json.loads(kwargs["filters"])
    assert parsed == {"fa_pe": "u20"}


def test_filters_file_loaded_into_json_string(mock_runner: MagicMock, tmp_path: Path) -> None:
    """`--filters-file PATH` reads the file content and forwards as the JSON string."""
    file_path = tmp_path / "filters.json"
    file_path.write_text('{"fa_pe":"u20","sec":"energy"}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(run_main, ["--filters-file", str(file_path)])
    assert result.exit_code == 0, result.output

    mock_runner.assert_called_once()
    kwargs = mock_runner.call_args.kwargs
    parsed = json.loads(kwargs["filters"])
    assert parsed == {"fa_pe": "u20", "sec": "energy"}


def test_filters_file_nonexistent_path_rejected_by_click() -> None:
    """Click's path validator rejects a missing file before the orchestrator runs."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filters-file", "definitely_not_here.json"])
    assert result.exit_code != 0
    # Click's standard "does not exist" message.
    assert "exist" in result.output.lower() or "not" in result.output.lower()


# ---------------------------------------------------------------------------
# Mutual-exclusion — every pair of input modes fails with the canonical msg.
# ---------------------------------------------------------------------------


_MUTEX_MSG_FRAGMENT = "mutually exclusive"


def test_filter_and_history_mutually_exclusive() -> None:
    """`--filter` + `--history` → exit 2 with mutex message and no traceback."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "fa_pe=u20", "--history"])
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output


def test_filter_and_scrape_link_mutually_exclusive() -> None:
    """`--filter` + `--scrape-link` → exit 2 with no traceback."""
    runner = CliRunner()
    result = runner.invoke(
        run_main,
        ["--filter", "fa_pe=u20", "--scrape-link", "https://finviz.com/x"],
    )
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output


def test_filters_json_and_filters_file_mutually_exclusive(tmp_path: Path) -> None:
    """`--filters-json` + `--filters-file` → exit 2 (canonical scenario from §7.2)."""
    file_path = tmp_path / "filters.json"
    file_path.write_text('{"sec":"energy"}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        run_main,
        ["--filters-json", '{"fa_pe":"u20"}', "--filters-file", str(file_path)],
    )
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output


def test_filter_and_filters_json_mutually_exclusive() -> None:
    """`--filter` + `--filters-json` → exit 2."""
    runner = CliRunner()
    result = runner.invoke(
        run_main,
        ["--filter", "fa_pe=u20", "--filters-json", '{"sec":"energy"}'],
    )
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output


def test_history_and_filters_file_mutually_exclusive(tmp_path: Path) -> None:
    """`--history` + `--filters-file` → exit 2."""
    file_path = tmp_path / "filters.json"
    file_path.write_text('{"sec":"energy"}', encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(run_main, ["--history", "--filters-file", str(file_path)])
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output


def test_history_and_scrape_link_still_mutex() -> None:
    """Pre-existing pairing must continue to fail (back-compat)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--history", "--scrape-link", "https://finviz.com/x"])
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Malformed `--filter` token handling.
# ---------------------------------------------------------------------------


def test_filter_without_equals_rejected() -> None:
    """A `--filter` token missing `=` exits 2 and names the offender."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "no_equals_here"])
    assert result.exit_code == 2
    assert "no_equals_here" in result.output
    assert "Traceback" not in result.output


def test_filter_empty_key_rejected() -> None:
    """`--filter =value` is rejected with exit 2 and no traceback."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "=u20"])
    assert result.exit_code == 2
    assert "Traceback" not in result.output


def test_filter_empty_value_rejected() -> None:
    """`--filter key=` is rejected (empty value-code is the 'Any' sentinel and
    legal in the registry, but bare empty in CLI input is almost certainly a
    user mistake — reject so silent no-op runs cannot happen)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "fa_pe="])
    assert result.exit_code == 2
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# Unknown key / value surfaces as a CLI error (validator chained from
# build_config). These tests do invoke build_config (which calls the
# validator) but mock out the screener pipeline so no HTTP fires.
# ---------------------------------------------------------------------------


def test_unknown_filter_key_exits_2_with_clean_message() -> None:
    """Unknown filter key → exit 2 (Click's UsageError) with the offending key
    named and no Python traceback in the output.

    Patches `build_config` to invoke the real validator (without depending
    on the orchestrator pipeline). Cleaner than mocking out `run_stock_screener`
    here because validation must fire before any HTTP fetch is attempted.
    """
    runner = CliRunner()
    # Stub `fetch_page_sync` so the test never reaches the network even if
    # validation regresses. The real `build_config` (and hence the validator)
    # runs because we don't mock `run_stock_screener` here.
    with patch("fincli.app.main.fetch_page_sync") as fetch_mock:
        fetch_mock.return_value = b"<html></html>"
        result = runner.invoke(run_main, ["--filter", "bogus_key=u20"])

    assert result.exit_code == 2
    assert "bogus_key" in result.output
    assert "Traceback" not in result.output
    # Validator must reject before any HTTP fetch happens.
    assert fetch_mock.call_count == 0


def test_unknown_value_for_known_key_exits_2_with_clean_message() -> None:
    """Unknown value for known key → exit 2, message names both, no traceback."""
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync") as fetch_mock:
        fetch_mock.return_value = b"<html></html>"
        result = runner.invoke(run_main, ["--filter", "fa_pe=bogus_value"])

    assert result.exit_code == 2
    assert "bogus_value" in result.output
    assert "fa_pe" in result.output
    assert "Traceback" not in result.output
    assert fetch_mock.call_count == 0


def test_filters_json_list_shape_exits_2_with_clean_message() -> None:
    """Legacy `[["k","v"]]` shape → exit 2 (schema lockdown).

    Pins spec §7.2 line 358: schema-rejection is exit 2 with a clean
    UsageError message, never exit 1 with a Python traceback. The
    `ValueError` raised by `json_to_tuples` is translated to
    `click.UsageError` at the CLI boundary.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync") as fetch_mock:
        fetch_mock.return_value = b"<html></html>"
        result = runner.invoke(run_main, ["--filters-json", '[["fa_pe","u20"]]'])

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    # The configurator's error message names the bad shape ("list").
    assert "list" in result.output
    assert fetch_mock.call_count == 0


def test_filters_json_non_string_value_exits_2_with_clean_message() -> None:
    """`{"fa_pe":42}` (non-string value) → exit 2, clean message, no traceback.

    Covers the second leg of the `json_to_tuples` ValueError contract: flat
    object but with a non-string value. Spec §5.1 step 3 schema lockdown.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync") as fetch_mock:
        fetch_mock.return_value = b"<html></html>"
        result = runner.invoke(run_main, ["--filters-json", '{"fa_pe":42}'])

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    # Message names the offending key and the bad type.
    assert "fa_pe" in result.output
    assert fetch_mock.call_count == 0


def test_filters_json_malformed_exits_2_with_clean_message() -> None:
    """`--filters-json 'not json at all'` → exit 2, clean message, no traceback.

    `json.JSONDecodeError` is a `ValueError` subclass, so the CLI boundary
    wrap covers it too. Spec §7.2 exit-2 contract.
    """
    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync") as fetch_mock:
        fetch_mock.return_value = b"<html></html>"
        result = runner.invoke(run_main, ["--filters-json", "not json at all"])

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert fetch_mock.call_count == 0


def test_filters_file_malformed_content_exits_2_with_clean_message(tmp_path: Path) -> None:
    """`--filters-file <path>` with malformed JSON content → exit 2, clean message.

    The file-read path converges into the same `json_to_tuples` call inside
    `build_config`, so the CLI boundary wrap applies here too.
    """
    bad_file = tmp_path / "malformed.json"
    bad_file.write_text("not json at all", encoding="utf-8")

    runner = CliRunner()
    with patch("fincli.app.main.fetch_page_sync") as fetch_mock:
        fetch_mock.return_value = b"<html></html>"
        result = runner.invoke(run_main, ["--filters-file", str(bad_file)])

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert fetch_mock.call_count == 0


# ---------------------------------------------------------------------------
# Back-compat — today's options still parse.
# ---------------------------------------------------------------------------


def test_no_flags_still_routes_to_interactive(mock_runner: MagicMock) -> None:
    """`fincli` with no input-mode flags forwards an empty filters string
    (interactive mode marker) to `run_stock_screener`."""
    runner = CliRunner()
    result = runner.invoke(run_main, [])
    assert result.exit_code == 0
    mock_runner.assert_called_once()
    kwargs = mock_runner.call_args.kwargs
    # Empty string == "fall through to interactive selection".
    assert kwargs.get("filters", "") == ""


def test_history_alone_still_works(mock_runner: MagicMock) -> None:
    """`--history` alone forwards `history=True, filters=""`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--history"])
    assert result.exit_code == 0
    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("history") is True
    assert kwargs.get("filters", "") == ""


def test_scrape_link_alone_still_works(mock_runner: MagicMock) -> None:
    """`--scrape-link` alone forwards `scrape_link=<url>, filters=""`."""
    runner = CliRunner()
    url = "https://finviz.com/screener.ashx?v=111&f=foo"
    result = runner.invoke(run_main, ["--scrape-link", url])
    assert result.exit_code == 0
    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("scrape_link") == url
    assert kwargs.get("filters", "") == ""


# ---------------------------------------------------------------------------
# Pillar 3 — `--quiet` / `--json-summary` CLI surface tests. End-to-end
# behavioral assertions live in `tests/integration/test_pipeline_streaming.py`
# and `tests/integration/test_pipeline_summary.py`; this block pins parser
# shape only (option presence, alias, orthogonality, kwarg threading).
# ---------------------------------------------------------------------------


def test_quiet_option_in_help() -> None:
    """`--quiet` appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--quiet" in result.output


def test_quiet_short_alias_in_help() -> None:
    """`-q` short alias appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "-q" in result.output


def test_json_summary_option_in_help() -> None:
    """`--json-summary` appears in `--help` output."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--json-summary" in result.output


def test_quiet_long_form_threads_true(mock_runner: MagicMock) -> None:
    """`--quiet` forwards `quiet=True` to `run_stock_screener`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--quiet"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("quiet") is True


def test_quiet_short_form_threads_true(mock_runner: MagicMock) -> None:
    """`-q` short form forwards `quiet=True`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["-q"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("quiet") is True


def test_json_summary_threads_true(mock_runner: MagicMock) -> None:
    """`--json-summary` forwards `json_summary=True`."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--json-summary"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("json_summary") is True


def test_no_pillar3_flags_thread_false(mock_runner: MagicMock) -> None:
    """Back-compat: omitting both flags forwards `quiet=False, json_summary=False`."""
    runner = CliRunner()
    result = runner.invoke(run_main, [])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("quiet") is False
    assert kwargs.get("json_summary") is False


def test_quiet_composes_with_filter_flag(mock_runner: MagicMock) -> None:
    """`--filter ... --quiet` is a valid combination (orthogonal to input modes)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--filter", "fa_pe=u20", "--quiet"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("quiet") is True
    assert kwargs.get("filters")  # non-empty JSON


def test_json_summary_composes_with_output_flag(mock_runner: MagicMock) -> None:
    """`--output PATH --json-summary` is a valid combination."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--output", "./out.csv", "--json-summary"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("output_path") == "./out.csv"
    assert kwargs.get("json_summary") is True


def test_quiet_composes_with_json_summary(mock_runner: MagicMock) -> None:
    """`--quiet --json-summary` is a valid combination (both orthogonal flags)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--quiet", "--json-summary"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("quiet") is True
    assert kwargs.get("json_summary") is True


def test_quiet_composes_with_debug(mock_runner: MagicMock) -> None:
    """`--debug --quiet` is a valid combination — see spec §7.4 row 6.

    The semantic contract (debug records still hit file handlers under
    `--quiet`) is exercised by the integration tests; this assertion only
    pins that the CLI parser accepts both flags together.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--debug", "--quiet"])
    assert result.exit_code == 0, result.output

    kwargs = mock_runner.call_args.kwargs
    assert kwargs.get("debug") is True
    assert kwargs.get("quiet") is True
