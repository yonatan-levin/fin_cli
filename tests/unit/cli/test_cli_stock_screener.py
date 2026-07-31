"""Tests for `fincli.cli.cli_stock_screener.select_filters_and_values`.

Pillar 1 adds two changes to this function (spec §5.1 steps 4 + 6):

1. **Early-return** — when `config.filters` is non-empty (and not in history /
   scrape-link mode), skip the interactive picker entirely and build the
   query directly. This is what makes structured input usable end-to-end.

2. **Writeback fix** — `filter_history.json` must be overwritten on every
   successful run that produced a non-empty filter set, regardless of input
   mode. The pre-existing code gated the write inside `if config.use_history:`
   which meant it never executed (the read branch already returned). This
   test pins the corrected behavior so subsequent refactors keep the bug
   fixed.

`--scrape-link` deliberately skips the writeback (no filter set to record).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import click
import pytest

from config.config import Config
from fincli.cli.cli_stock_screener import (
    _write_history,
    prompt_section,
    select_filters_and_values,
)

# ---------------------------------------------------------------------------
# Early-return path — config.filters preloaded by structured input.
# ---------------------------------------------------------------------------


def test_early_return_with_preloaded_filters(tmp_path: Path) -> None:
    """When `config.filters` is preloaded (from --filter / --filters-json /
    --filters-file), the picker is skipped and a query URL is built directly."""
    config = Config(
        filters=(("fa_pe", "u20"), ("sec", "energy")),
        history_dir=tmp_path,
    )

    query = select_filters_and_values(config)

    # The build_stock_screener_query output should embed both filter codes.
    assert isinstance(query, str)
    assert "fa_pe_u20" in query
    assert "sec_energy" in query


def test_early_return_writes_filter_history(tmp_path: Path) -> None:
    """Non-interactive runs with non-empty filters must persist the selection
    to `<history_dir>/filter_history.json`. This is the §7.2 writeback
    acceptance: a subsequent `fincli --history` recovers them."""
    config = Config(
        filters=(("fa_pe", "u20"), ("sec", "energy")),
        history_dir=tmp_path,
    )

    select_filters_and_values(config)

    history_path = tmp_path / "filter_history.json"
    assert history_path.exists(), "writeback did not create the history file"

    persisted = json.loads(history_path.read_text(encoding="utf-8"))
    assert persisted == {"fa_pe": "u20", "sec": "energy"}


def test_early_return_overwrites_existing_history(tmp_path: Path) -> None:
    """The writeback overwrites prior history (matches CONTRACTS §4.3 — the
    file is overwritten on every successful run)."""
    history_path = tmp_path / "filter_history.json"
    history_path.write_text('{"old_key":"old_value"}', encoding="utf-8")

    config = Config(
        filters=(("sec", "technology"),),
        history_dir=tmp_path,
    )

    select_filters_and_values(config)

    persisted = json.loads(history_path.read_text(encoding="utf-8"))
    assert persisted == {"sec": "technology"}
    assert "old_key" not in persisted


# ---------------------------------------------------------------------------
# Use-history path — read existing history, build query, do NOT re-write
# (read path is a no-op for the writeback chokepoint; the file is already
# the source of truth).
# ---------------------------------------------------------------------------


def test_use_history_path_builds_query_from_disk(tmp_path: Path) -> None:
    """`use_history=True` reads the JSON file and builds the query from it."""
    history_path = tmp_path / "filter_history.json"
    history_path.write_text('{"fa_pe":"u20","sec":"energy"}', encoding="utf-8")

    config = Config(use_history=True, history_dir=tmp_path)

    query = select_filters_and_values(config)
    assert "fa_pe_u20" in query
    assert "sec_energy" in query


# ---------------------------------------------------------------------------
# Scrape-link guard — early-return must NOT fire when scrape_link is set
# (orchestrator handles that path separately; if filters happen to be set
# alongside, behavior here would be undefined). The CLI's mutex check
# rules out this combination, but the function-level guard is defensive.
# ---------------------------------------------------------------------------


def test_scrape_link_does_not_trigger_early_return(tmp_path: Path) -> None:
    """A ``Config`` with both ``scrape_link`` and ``filters`` set is theoretically
    impossible via the CLI (the mutex check rules it out), but the function
    contains a defensive guard at the function level: the early-return must
    NOT fire because ``--scrape-link`` semantics say 'use the URL verbatim,
    ignore everything else'.

    Patch the section prompts to represent an interactive user who skips every
    section. This proves the preloaded filters are ignored on the defensive
    scrape-link combination and that no history is written.
    """
    config = Config(
        filters=(("fa_pe", "u20"),),
        scrape_link="https://finviz.com/screener.ashx?v=111",
        history_dir=tmp_path,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "fincli.cli.cli_stock_screener.prompt_section",
            lambda *_args, **_kwargs: [],
        )
        query = select_filters_and_values(config)

    assert "fa_pe_u20" not in query
    assert not (tmp_path / "filter_history.json").exists()


def test_interactive_picker_builds_query_and_writes_history(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real interactive selection traverses all sections and persists it."""
    responses: Iterator[str | int] = iter(("1", "", "", 2))
    monkeypatch.setattr(click, "prompt", lambda *_args, **_kwargs: next(responses))
    config = Config(history_dir=tmp_path)

    query = select_filters_and_values(config)

    assert "fa_pe_low" in query
    assert json.loads((tmp_path / "filter_history.json").read_text(encoding="utf-8")) == {
        "fa_pe": "low"
    }


def test_prompt_section_reprompts_for_invalid_and_out_of_range_input(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid text and an out-of-range index are rejected before acceptance."""

    class OneFilter:
        ONLY = ["fa_pe", {"u5": "Under 5"}]

    responses = iter(("not-a-number", "2", "1"))
    monkeypatch.setattr(click, "prompt", lambda *_args, **_kwargs: next(responses))

    selected = prompt_section(
        OneFilter,
        {"ONLY": {"u5": "Under 5"}},
        "Test Params",
    )

    assert selected == [{"ONLY": {"u5": "Under 5"}}]
    output = capsys.readouterr().out
    assert "expected comma-separated integers" in output
    assert "out of range" in output


def test_empty_history_selection_does_not_create_file(tmp_path: Path) -> None:
    """Skipping every filter is not recorded as a reusable history entry."""
    _write_history(Config(history_dir=tmp_path), {})

    assert not (tmp_path / "filter_history.json").exists()
