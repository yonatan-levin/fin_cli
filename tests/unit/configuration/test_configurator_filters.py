"""Tests for `core.configuration.configurator.build_config` filter wiring.

Pillar 1 (docs/features/pipeline-mode-spec.md §5.1) routes every structured
input form through `build_config(filters=<json-string>)`. This file pins the
contract:

  - A non-empty JSON string populates `config.filters` via `json_to_tuples`.
  - Validation (`validate_filter_pairs`) runs immediately after parse so
    unknown keys/values surface as `click.UsageError` (CLI exit 2).
  - `use_history` precedence over `filters` is preserved (history wins —
    matches the legacy `if filters != "" and not use_history` guard).
  - `--scrape-link` does not invoke the validator (URL is opaque).
"""

from __future__ import annotations

import click
import pytest

from core.configuration.configurator import build_config

# ---------------------------------------------------------------------------
# Happy path — JSON string parses into the tuple shape on Config.filters.
# ---------------------------------------------------------------------------


def test_filters_json_populates_config_filters() -> None:
    """A flat-object JSON string becomes `config.filters` as tuple-of-pairs."""
    config = build_config(filters='{"fa_pe":"u20","sec":"energy"}')
    assert config.filters == (("fa_pe", "u20"), ("sec", "energy"))


def test_empty_filters_string_leaves_default() -> None:
    """The empty default — interactive mode, no filters preloaded."""
    config = build_config(filters="")
    assert config.filters == ()


def test_single_pair_filters() -> None:
    """A single-pair JSON string produces a one-tuple filters value."""
    config = build_config(filters='{"fa_pe":"u20"}')
    assert config.filters == (("fa_pe", "u20"),)


# ---------------------------------------------------------------------------
# Strict validation — unknown key / value rejected at the configurator.
# ---------------------------------------------------------------------------


def test_unknown_key_raises_usage_error() -> None:
    """Unknown filter key surfaces as a `click.UsageError` from build_config —
    the single chokepoint for structured-input validation (spec §5.1 step 5)."""
    with pytest.raises(click.UsageError) as excinfo:
        build_config(filters='{"bogus_key":"u20"}')
    assert "bogus_key" in str(excinfo.value)


def test_unknown_value_raises_usage_error() -> None:
    """Unknown value-for-known-key also surfaces as `click.UsageError`."""
    with pytest.raises(click.UsageError) as excinfo:
        build_config(filters='{"fa_pe":"bogus_value"}')
    assert "bogus_value" in str(excinfo.value)
    assert "fa_pe" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Schema lockdown propagates from json_to_tuples (list shape rejected).
# ---------------------------------------------------------------------------


def test_list_shape_filters_raises_value_error() -> None:
    """Legacy list-of-pairs JSON shape no longer accepted (§5.1 step 3)."""
    # `json_to_tuples` raises ValueError; the CLI translates to UsageError.
    # `build_config` itself just lets the ValueError propagate.
    with pytest.raises((ValueError, click.UsageError)):
        build_config(filters='[["fa_pe","u20"]]')


# ---------------------------------------------------------------------------
# Precedence — `use_history=True` wins over a `filters` argument.
# ---------------------------------------------------------------------------


def test_use_history_skips_filters_argument(tmp_path, monkeypatch) -> None:
    """When `use_history=True`, the `filters` JSON string is ignored — history
    is read from disk instead. Matches legacy guard at configurator.py:34."""
    # Set up a history file in an isolated temp dir.
    monkeypatch.setenv("HISTORY_DIR", str(tmp_path))
    history_file = tmp_path / "filter_history.json"
    history_file.write_text('{"sec":"energy"}', encoding="utf-8")

    # Pass a different filters JSON; history should win.
    config = build_config(use_history=True, filters='{"fa_pe":"u20"}')

    # The values from the history file end up in `filters`, not the argument.
    assert ("sec", "energy") in config.filters
    assert ("fa_pe", "u20") not in config.filters


# ---------------------------------------------------------------------------
# Scrape-link path — does not run the validator (URL is opaque).
# ---------------------------------------------------------------------------


def test_scrape_link_skips_filter_validator() -> None:
    """`--scrape-link` does not invoke filter validation — the URL is opaque
    and the filters tuple stays empty."""
    config = build_config(scrape_link="https://finviz.com/screener.ashx?v=111&f=foo_bar")
    assert config.filters == ()
    assert config.scrape_link == "https://finviz.com/screener.ashx?v=111&f=foo_bar"
