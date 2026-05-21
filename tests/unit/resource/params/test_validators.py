"""Tests for `fincli.resource.params.validators`.

Covers `validate_filter_pairs` (raises `click.UsageError` on unknown key or
unknown value-for-known-key) and `list_valid_filters` (returns the canonical
{query_key: [value_codes...]} mapping that powers the error messages and the
future `--help-filters` CLI flag — see `docs/features/archive/pipeline-mode-spec.md`
§5.1 step 5).

The validator is the single chokepoint that closes the silent-drop hazard at
`quary_builders.py:18-22` for structured input. Interactive picker UI is
already validated; `--scrape-link` and `--history` skip this validator (URL
is opaque; history was previously valid by construction).
"""

from __future__ import annotations

import click
import pytest

from fincli.resource.params.validators import (
    list_valid_filters,
    list_valid_filters_with_labels,
    validate_filter_pairs,
)

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


# ---------------------------------------------------------------------------
# `list_valid_filters_with_labels` helper — spec §5.4 sibling that adds
# human labels (key label via `attr_to_label` + preserved value-label map).
#
# Tests below pin the spec §7.4 invariants at the HELPER layer; the
# end-to-end CLI surface (parsing stdout JSON, etc.) is exercised by T2's
# integration tests.
# ---------------------------------------------------------------------------


def test_list_valid_filters_with_labels_returns_dict_shape() -> None:
    """Top-level shape: ``dict[str, dict[str, object]]`` with at least one
    entry from each of the three param classes."""
    inventory = list_valid_filters_with_labels()

    assert isinstance(inventory, dict)
    assert "fa_pe" in inventory, "Fundamental entry missing"
    assert "sec" in inventory, "Descriptive entry missing"
    assert "ta_rsi" in inventory, "Technical entry missing"


def test_list_valid_filters_with_labels_entry_has_label_and_values_keys() -> None:
    """Every entry has exactly the two keys ``{'label', 'values'}`` —
    extra keys would silently expand the spec §5.2 schema.

    Pins the per-entry shape so a future addition (e.g., 'description',
    'group') is a conscious schema_version bump rather than an accidental
    extra field that downstream Go consumers see and ignore.
    """
    inventory = list_valid_filters_with_labels()

    for key, entry in inventory.items():
        assert isinstance(entry, dict), f"{key} entry is {type(entry)}"
        assert set(entry.keys()) == {"label", "values"}, (
            f"{key} entry has keys {sorted(entry.keys())!r}, expected {{'label', 'values'}}"
        )


def test_list_valid_filters_with_labels_label_is_nonempty_string() -> None:
    """Every ``entry['label']`` is a non-empty string. Empty labels would
    produce blank dropdown headers downstream."""
    inventory = list_valid_filters_with_labels()

    for key, entry in inventory.items():
        label = entry["label"]
        assert isinstance(label, str), f"{key}.label is {type(label)}"
        assert label, f"{key}.label is empty string"


def test_list_valid_filters_with_labels_values_is_str_to_str_dict() -> None:
    """Every ``entry['values']`` is a ``dict[str, str]`` — both code and
    label sides are strings (matches the JSON shape promised by the
    inventory dump contract)."""
    inventory = list_valid_filters_with_labels()

    for key, entry in inventory.items():
        values = entry["values"]
        assert isinstance(values, dict), f"{key}.values is {type(values)}"
        assert values, f"{key}.values is empty dict"
        for code, label in values.items():
            assert isinstance(code, str), f"{key}.values code {code!r} is {type(code)}"
            assert isinstance(label, str), f"{key}.values[{code!r}] is {type(label)}"


def test_list_valid_filters_with_labels_preserves_empty_string_value_code() -> None:
    """The empty-string value code (the 'Any' sentinel) is registered on
    every entry and MUST survive into the labelled inventory — the validator
    accepts ``""`` as a legal value (see test_known_key_with_empty_string_value_passes).
    """
    inventory = list_valid_filters_with_labels()

    fa_pe_values = inventory["fa_pe"]["values"]
    assert isinstance(fa_pe_values, dict)
    assert fa_pe_values.get("") == "Any", (
        f"Empty-string sentinel dropped or relabelled; got {fa_pe_values.get('')!r}"
    )


def test_list_valid_filters_with_labels_known_label_samples() -> None:
    """Spot-check the §7.4 content invariants at the helper layer.

    These same assertions appear in T2's integration test in their
    end-to-end form (parsing JSON off stdout). Pinning them at the helper
    layer lets T1 ship and regress independently of CLI wiring.
    """
    inventory = list_valid_filters_with_labels()

    assert inventory["fa_pe"]["label"] == "PE"
    assert inventory["sec"]["label"] == "Sector"
    assert inventory["ta_rsi"]["label"] == "RSI 14"


def test_list_valid_filters_with_labels_known_value_samples() -> None:
    """Spot-check known value labels survive the walker."""
    inventory = list_valid_filters_with_labels()

    fa_pe_values = inventory["fa_pe"]["values"]
    sec_values = inventory["sec"]["values"]
    assert isinstance(fa_pe_values, dict)
    assert isinstance(sec_values, dict)

    assert fa_pe_values["u20"] == "Under 20"
    assert sec_values["basicmaterials"] == "Basic Materials"


def test_list_valid_filters_with_labels_insertion_order_fundamental_first() -> None:
    """Insertion order is Fundamental → Descriptive → Technical (matches
    `_PARAM_CLASSES` declaration order).

    Pins the canonical ordering contract the upcoming `--list-filters --json`
    `keys` field relies on (spec §5.2). A regression that re-orders the
    walker would silently break Go consumers iterating the `keys` array.
    """
    inventory = list_valid_filters_with_labels()
    keys = list(inventory.keys())

    fa_pe_idx = keys.index("fa_pe")  # Fundamental
    sec_idx = keys.index("sec")  # Descriptive
    ta_rsi_idx = keys.index("ta_rsi")  # Technical

    assert fa_pe_idx < sec_idx, (
        f"Fundamental ('fa_pe' at {fa_pe_idx}) must precede Descriptive ('sec' at {sec_idx})"
    )
    assert sec_idx < ta_rsi_idx, (
        f"Descriptive ('sec' at {sec_idx}) must precede Technical ('ta_rsi' at {ta_rsi_idx})"
    )


def test_list_valid_filters_with_labels_keys_match_list_valid_filters() -> None:
    """The two sibling helpers MUST advertise the same universe of query
    keys. Divergence would mean the labelled inventory is missing entries
    the validator considers legal (or vice versa) — a polyglot consumer
    would then validate against one set and dropdown-render the other.
    """
    codes_inventory = list_valid_filters()
    labels_inventory = list_valid_filters_with_labels()

    assert list(codes_inventory.keys()) == list(labels_inventory.keys()), (
        "list_valid_filters and list_valid_filters_with_labels disagree on "
        "either the membership or the order of registered query keys."
    )
