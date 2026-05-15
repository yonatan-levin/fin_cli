"""Tests for `fincli.resource.params.validators`.

Covers `validate_filter_pairs` (raises `click.UsageError` on unknown key or
unknown value-for-known-key) and `list_valid_filters` (returns the canonical
{query_key: [value_codes...]} mapping that powers the error messages and the
future `--help-filters` CLI flag — see `docs/features/pipeline-mode-spec.md`
§5.1 step 5).

The validator is the single chokepoint that closes the silent-drop hazard at
`quary_builders.py:18-22` for structured input. Interactive picker UI is
already validated; `--scrape-link` and `--history` skip this validator (URL
is opaque; history was previously valid by construction).
"""

from __future__ import annotations

import click
import pytest

from fincli.resource.params.validators import list_valid_filters, validate_filter_pairs

# ---------------------------------------------------------------------------
# Happy paths — known keys + known value codes pass silently.
# ---------------------------------------------------------------------------


def test_known_pair_passes_silently() -> None:
    """A registered (key, value) pair raises nothing."""
    validate_filter_pairs((("fa_pe", "u20"),))


def test_multiple_known_pairs_pass() -> None:
    """Several registered pairs across param classes all pass."""
    validate_filter_pairs(
        (
            ("fa_pe", "u20"),
            ("sec", "energy"),
            ("ta_rsi", "ob70"),
        )
    )


def test_empty_tuple_passes() -> None:
    """No pairs to check → no error. Caller decides what 'no filters' means."""
    validate_filter_pairs(())


def test_known_key_with_empty_string_value_passes() -> None:
    """Empty-string value codes (the 'Any' sentinel) are registered values
    and must be accepted by the validator."""
    validate_filter_pairs((("fa_pe", ""),))


# ---------------------------------------------------------------------------
# Unknown key — UsageError, message names the offending key.
# ---------------------------------------------------------------------------


def test_unknown_key_raises_usage_error() -> None:
    """Unknown query_key raises `click.UsageError`."""
    with pytest.raises(click.UsageError) as excinfo:
        validate_filter_pairs((("bogus_key", "u20"),))

    msg = str(excinfo.value)
    assert "bogus_key" in msg, f"Error must name the offending key; got {msg!r}"
    assert "key" in msg.lower() or "filter" in msg.lower()


def test_unknown_key_message_lists_valid_alternatives() -> None:
    """The error message must include some valid sibling keys to aid recovery."""
    with pytest.raises(click.UsageError) as excinfo:
        validate_filter_pairs((("bogus_key", "u20"),))

    msg = str(excinfo.value)
    # At least one known key from each major params file should be a candidate
    # suggestion. We don't pin the exact 10-entry slice, just that recovery
    # info is present.
    assert "fa_pe" in msg or "sec" in msg or "ta_rsi" in msg, (
        f"Expected at least one valid key suggestion in message; got {msg!r}"
    )


# ---------------------------------------------------------------------------
# Unknown value-for-known-key — UsageError, message names key + value.
# ---------------------------------------------------------------------------


def test_unknown_value_for_known_key_raises_usage_error() -> None:
    """Known key + unknown value → UsageError naming both."""
    with pytest.raises(click.UsageError) as excinfo:
        validate_filter_pairs((("fa_pe", "bogus_value"),))

    msg = str(excinfo.value)
    assert "bogus_value" in msg, f"Error must name the offending value; got {msg!r}"
    assert "fa_pe" in msg, f"Error must name the parent key; got {msg!r}"


def test_unknown_value_message_lists_valid_alternatives() -> None:
    """The error message must include some valid sibling value codes."""
    with pytest.raises(click.UsageError) as excinfo:
        validate_filter_pairs((("fa_pe", "bogus_value"),))

    msg = str(excinfo.value)
    # Pick a couple of well-known fa_pe value codes that should appear in any
    # truncated suggestion list (the dict iteration order is insertion order
    # so the early entries are stable).
    assert "u20" in msg or "low" in msg or "high" in msg, (
        f"Expected a valid value suggestion in message; got {msg!r}"
    )


# ---------------------------------------------------------------------------
# `list_valid_filters` helper — exposes the inventory.
# ---------------------------------------------------------------------------


def test_list_valid_filters_returns_dict_of_keys_to_value_codes() -> None:
    """Helper returns a dict mapping every registered query_key to the list
    of valid value codes."""
    inventory = list_valid_filters()

    assert isinstance(inventory, dict)
    assert "fa_pe" in inventory
    assert "sec" in inventory
    assert "ta_rsi" in inventory


def test_list_valid_filters_value_codes_are_strings() -> None:
    """Every value code in the inventory is a string (matches the JSON shape
    enforced by `json_to_tuples`)."""
    inventory = list_valid_filters()

    for key, codes in inventory.items():
        assert isinstance(codes, list), f"{key} mapped to {type(codes)}"
        for code in codes:
            assert isinstance(code, str), f"{key} contains non-string code: {code!r}"


def test_list_valid_filters_includes_known_codes() -> None:
    """Spot-check a handful of well-known codes."""
    inventory = list_valid_filters()
    assert "u20" in inventory["fa_pe"]
    assert "energy" in inventory["sec"]
    assert "ob70" in inventory["ta_rsi"]


# ---------------------------------------------------------------------------
# Round-trip: validator agrees with the inventory it exposes.
# ---------------------------------------------------------------------------


def test_inventory_round_trips_through_validator() -> None:
    """Every (key, code) the inventory advertises must validate cleanly. This
    is the safety net that the validator and the helper agree on the same
    universe of pairs."""
    inventory = list_valid_filters()

    # Pick a representative subset to keep the test fast — every key, first
    # value only.
    pairs = tuple((key, codes[0]) for key, codes in inventory.items() if codes)

    # If this raises, the validator and the inventory have diverged.
    validate_filter_pairs(pairs)
