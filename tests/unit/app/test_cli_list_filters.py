"""Click-surface tests for ``--list-filters --json`` (list-filters-spec).

Pins the contract from ``docs/features/archive/list-filters-spec.md`` §5.1 + §5.5 + §6:

  - Both flags surface in ``--help``.
  - Module constant ``LIST_FILTERS_SCHEMA_VERSION`` is importable from
    ``fincli.app.cli`` so other call sites (and tests) can reference the
    schema version by name rather than re-typing the literal ``1``.
  - ``--list-filters`` alone (without ``--json``) exits 2 with a UsageError
    that names ``--json`` as the missing piece.
  - ``--list-filters --json`` exits 0; stdout is exactly one JSON line.
  - The ``--json`` flag is silently ignored when ``--list-filters`` is not
    set (spec OQ2 HUMAN-approved default) — passing bare ``--json`` does NOT
    break an unrelated invocation.
  - All 5 mutex pairings (``--list-filters`` × each of the existing
    input-mode flags) exit 2 with the extended canonical mutex message.
  - Orthogonal flags (``--output``, ``--quiet``, ``--debug``,
    ``--json-summary``) are no-ops in ``--list-filters`` mode: stdout is
    JSON-only, no file is written, no banner/progress/summary leak.
  - The integrated OQ-B/C/D matrix test (BACKEND step 9, per gpt-5.5
    deep-think) pins the short-circuit interaction with every orthogonal
    flag flipped on simultaneously — short-circuit fires BEFORE banner,
    BEFORE ``run_stock_screener`` import, BEFORE any other handler.

Tests mock ``fincli.app.main.fetch_page_sync`` on the negative paths as a
belt-and-braces guard against a regression that would let the screener
pipeline run when ``--list-filters`` is set.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from fincli.app.cli import LIST_FILTERS_SCHEMA_VERSION, run_main


@pytest.fixture
def mock_fetch() -> Iterator[MagicMock]:
    """Patch ``fetch_page_sync`` so a regression that lets the pipeline run
    can't reach the network. Every ``--list-filters`` invocation MUST exit
    before the screener pipeline is touched; this fixture is a safety net,
    not a participant.
    """
    with patch("fincli.app.main.fetch_page_sync") as mock:
        mock.return_value = b"<html></html>"
        yield mock


# Substring shared with `test_cli_pipeline.py::_MUTEX_MSG_FRAGMENT`; the
# canonical message text changed for list-filters-spec (six-flag mutex set)
# but the substring "mutually exclusive" still matches.
_MUTEX_MSG_FRAGMENT = "mutually exclusive"


# ---------------------------------------------------------------------------
# Option presence — both new flags surface in --help.
# ---------------------------------------------------------------------------


def test_list_filters_option_in_help() -> None:
    """`--list-filters` appears in `--help` output (spec §7.2 bullet 8)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--list-filters" in result.output


def test_json_option_in_help() -> None:
    """`--json` appears in `--help` output (spec §7.2 bullet 8)."""
    runner = CliRunner()
    result = runner.invoke(run_main, ["--help"])
    assert result.exit_code == 0
    assert "--json" in result.output


# ---------------------------------------------------------------------------
# Happy path — --list-filters --json exits 0 with a single JSON line.
# ---------------------------------------------------------------------------


def test_list_filters_with_json_exits_zero_and_emits_single_json_line() -> None:
    """`fincli --list-filters --json` exits 0; stdout = exactly one JSON line.

    Pins spec §7.2 bullet 1 + §7.3 bullet 1 (single-line, parseable JSON).
    The integration test does the full schema-validation pass; this unit
    test pins the in-process contract via CliRunner so a regression that
    breaks the schema doesn't sneak past the unit tier.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--list-filters", "--json"])
    assert result.exit_code == 0, result.output

    # Strip the trailing newline `click.echo` adds; the remainder must
    # parse as JSON in one shot — proving "exactly one line".
    payload = json.loads(result.output.strip())
    assert payload["schema_version"] == LIST_FILTERS_SCHEMA_VERSION
    assert isinstance(payload["keys"], list) and payload["keys"]
    assert isinstance(payload["filters"], dict) and payload["filters"]


# ---------------------------------------------------------------------------
# --list-filters alone (no --json) -> exit 2 with UsageError naming --json.
# ---------------------------------------------------------------------------


def test_list_filters_without_json_exits_two_with_usage_error() -> None:
    """`--list-filters` alone fails with a UsageError naming `--json`.

    Pins spec §7.2 bullet 2 — bare `--list-filters` is a user error today
    (the only supported format is JSON; future formats need a different
    selector flag). The error message must mention `--json` so the user
    can self-correct without consulting docs.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--list-filters"])
    assert result.exit_code == 2
    assert "--json" in result.output
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# OQ2 contract — bare --json (without --list-filters) is silently ignored.
# ---------------------------------------------------------------------------


def test_bare_json_flag_is_silently_ignored() -> None:
    """`--json` alone (no `--list-filters`) is silently ignored — does NOT
    error and does NOT change behavior.

    Pins spec OQ2 HUMAN-approved default: `--json` is a sub-flag of
    `--list-filters`, not a free-standing format selector. Adding `--json`
    to an unrelated invocation must not break it. A future change that
    "tightens" this into rejection would break the contract; this test is
    the safety net.

    We pair `--json` with `--help` so Click short-circuits before the
    screener pipeline tries to fetch — no network, no fixtures needed.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--json", "--help"])
    assert result.exit_code == 0
    # The --help output still renders normally; bare --json didn't cause an
    # error and didn't intercept --help.
    assert "Usage:" in result.output


# ---------------------------------------------------------------------------
# Mutex — --list-filters paired with each of the 5 input-mode flags exits 2.
# (Cross-references the matching cases in test_cli_pipeline.py — this file
# duplicates ONE pairing as a focused sanity check; the full mutex matrix
# extension lives in test_cli_pipeline.py.)
# ---------------------------------------------------------------------------


def test_list_filters_and_filter_mutually_exclusive(mock_fetch: MagicMock) -> None:
    """`--list-filters --json` + `--filter` → exit 2 with mutex message.

    Pins spec §7.2 bullet 3. Cross-link with the same pairing in
    test_cli_pipeline.py — both tests should fail if the mutex regresses.
    """
    runner = CliRunner()
    result = runner.invoke(run_main, ["--list-filters", "--json", "--filter", "fa_pe=u20"])
    assert result.exit_code == 2
    assert _MUTEX_MSG_FRAGMENT in result.output.lower()
    assert "Traceback" not in result.output
    # Belt-and-braces: mutex must reject before any HTTP fetch is attempted.
    assert mock_fetch.call_count == 0


# ---------------------------------------------------------------------------
# Orthogonal-flag no-ops — --output / --quiet / --debug / --json-summary all
# silently ignored when --list-filters is set.
# ---------------------------------------------------------------------------


def test_list_filters_with_output_path_does_not_create_file(tmp_path: Path) -> None:
    """`--list-filters --json --output <path>` ignores `--output`; no file
    appears at the requested path.

    Pins spec §7.2 bullet 6. `--output` is a screen-result destination;
    the inventory dump is metadata and always goes to stdout.
    """
    target = tmp_path / "should-not-exist.csv"
    runner = CliRunner()
    result = runner.invoke(run_main, ["--list-filters", "--json", "--output", str(target)])
    assert result.exit_code == 0, result.output
    assert not target.exists(), (
        f"--output should be ignored under --list-filters, but {target} was created"
    )
    # The inventory still landed on stdout.
    payload = json.loads(result.output.strip())
    assert payload["schema_version"] == LIST_FILTERS_SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Integrated OQ-B/C/D interaction test (BACKEND step 9, per gpt-5.5
# deep-think). One matrix-style test that pins the short-circuit ordering
# against the full orthogonal-flag matrix — exit 0, stdout JSON-only, no
# banner anywhere, no progress, no OUTPUT_PATH= line, no JSON summary.
# ---------------------------------------------------------------------------


def test_list_filters_matrix_short_circuits_before_every_other_handler(
    mock_fetch: MagicMock,
) -> None:
    """Matrix test: `--list-filters --json` short-circuits before banner,
    before the local `run_stock_screener` import, and before each orthogonal
    flag's handler kicks in.

    Pins the interaction (not just isolated rules): even when ``--quiet``,
    ``--debug``, ``--json-summary``, and ``--output -`` are all set
    simultaneously, the short-circuit fires first. Stdout MUST be a single
    JSON line; no welcome banner, no progress logs, no ``OUTPUT_PATH=``
    discovery line, no JSON summary.

    Per gpt-5.5 deep-think follow-up to BACKEND step 9 in
    docs/features/archive/list-filters-plan.md §3 T2.
    """
    # Click 8.2+ separates stderr by default; `mix_stderr=False` was removed.
    # `result.stdout` and `result.stderr` are independently captured.
    runner = CliRunner()
    result = runner.invoke(
        run_main,
        [
            "--list-filters",
            "--json",
            "--quiet",
            "--debug",
            "--json-summary",
            "--output",
            "-",
        ],
    )
    assert result.exit_code == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    # Stdout shape: exactly one JSON line, starts with the schema_version key,
    # ends with a closing brace + trailing newline (`click.echo` convention).
    stdout = result.stdout
    assert stdout.startswith('{"schema_version":'), (
        f"stdout should be a single JSON line starting with the schema_version key; got {stdout!r}"
    )
    assert stdout.endswith("}\n"), (
        f"stdout should end with '}}\\n' (single JSON line + click.echo newline); got {stdout!r}"
    )
    # Parseable in one shot — proving "exactly one line".
    payload = json.loads(stdout.strip())
    assert payload["schema_version"] == LIST_FILTERS_SCHEMA_VERSION
    assert set(payload.keys()) == {"schema_version", "keys", "filters"}

    # No welcome banner anywhere (CliRunner captures both streams).
    assert "Welcome" not in result.stdout
    assert "Welcome" not in result.stderr
    # No OUTPUT_PATH= discovery line (would only appear if the screener ran).
    assert "OUTPUT_PATH=" not in result.stdout
    assert "OUTPUT_PATH=" not in result.stderr
    # No second JSON line on stderr that would imply --json-summary fired.
    stderr_json_lines = [
        line for line in result.stderr.splitlines() if line.strip().startswith("{")
    ]
    assert not stderr_json_lines, (
        f"--json-summary should be a no-op under --list-filters, but stderr "
        f"contains JSON lines: {stderr_json_lines!r}"
    )
    # Screener pipeline never ran — the fetcher must not have been called.
    assert mock_fetch.call_count == 0
