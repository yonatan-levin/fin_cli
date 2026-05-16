"""Schema-lockdown tests for `core.converters.json.json_to_tuples`.

The pipeline-mode spec (docs/features/archive/pipeline-mode-spec.md §5.1 step 3, OQ1
resolution) tightens the historic loose schema to a single canonical shape: a
flat JSON object whose keys and values are both strings. Lists, scalars,
nested objects, and non-string values are all rejected with `ValueError` so
the CLI can translate them into a clean `click.UsageError` (exit 2).

Empty dict is allowed and represents the "no filters" case; upstream callers
fall through to interactive selection when the resulting tuple is empty.

These tests are the contract; do not loosen them without a spec amendment.
"""

from __future__ import annotations

import pytest

from core.converters.json import json_to_tuples

# ---------------------------------------------------------------------------
# Happy paths — the dict-shape contract.
# ---------------------------------------------------------------------------


def test_flat_object_returns_tuple_of_pairs() -> None:
    """The canonical shape: flat JSON object becomes tuple of (key, value)."""
    result = json_to_tuples('{"fa_pe":"u20","sec":"energy"}')
    assert result == (("fa_pe", "u20"), ("sec", "energy"))


def test_single_key_object() -> None:
    """A one-key object still produces the tuple-of-pairs shape."""
    result = json_to_tuples('{"fa_pe":"u20"}')
    assert result == (("fa_pe", "u20"),)


def test_empty_object_returns_empty_tuple() -> None:
    """Empty dict is allowed — represents the no-filters case."""
    result = json_to_tuples("{}")
    assert result == ()


def test_single_quoted_input_normalized() -> None:
    """Single-quoted JSON-ish input is normalized (preserves the historic
    convenience for shells that strip double quotes)."""
    result = json_to_tuples("{'fa_pe':'u20'}")
    assert result == (("fa_pe", "u20"),)


# ---------------------------------------------------------------------------
# Rejected shapes — list, scalar, nested object, non-string value.
# ---------------------------------------------------------------------------


def test_list_of_pairs_rejected() -> None:
    """The legacy list-of-pairs shape is no longer accepted (OQ1)."""
    with pytest.raises(ValueError, match="object"):
        json_to_tuples('[["fa_pe","u20"]]')


def test_top_level_array_rejected() -> None:
    """Any top-level JSON array is rejected."""
    with pytest.raises(ValueError, match="object"):
        json_to_tuples('["fa_pe","u20"]')


def test_top_level_string_rejected() -> None:
    """Top-level scalar is rejected."""
    with pytest.raises(ValueError, match="object"):
        json_to_tuples('"hello"')


def test_top_level_number_rejected() -> None:
    """Top-level number is rejected."""
    with pytest.raises(ValueError, match="object"):
        json_to_tuples("42")


def test_top_level_null_rejected() -> None:
    """Top-level null is rejected."""
    with pytest.raises(ValueError, match="object"):
        json_to_tuples("null")


def test_top_level_bool_rejected() -> None:
    """Top-level boolean is rejected."""
    with pytest.raises(ValueError, match="object"):
        json_to_tuples("true")


def test_nested_object_value_rejected() -> None:
    """Nested-object values are rejected — keep the schema flat."""
    with pytest.raises(ValueError, match="string"):
        json_to_tuples('{"fa_pe":{"u20":"Under 20"}}')


def test_list_value_rejected() -> None:
    """List values are rejected — values must be strings."""
    with pytest.raises(ValueError, match="string"):
        json_to_tuples('{"fa_pe":["u20"]}')


def test_int_value_rejected() -> None:
    """Numeric values are rejected — Finviz value codes are strings."""
    with pytest.raises(ValueError, match="string"):
        json_to_tuples('{"fa_pe":20}')


def test_null_value_rejected() -> None:
    """Null values are rejected."""
    with pytest.raises(ValueError, match="string"):
        json_to_tuples('{"fa_pe":null}')


# ---------------------------------------------------------------------------
# Malformed JSON — propagates as ValueError (no bare prints).
# ---------------------------------------------------------------------------


def test_malformed_json_raises_value_error() -> None:
    """Invalid JSON raises ValueError (the legacy print+raise behavior is
    replaced with a clean raise so the CLI can translate to UsageError)."""
    with pytest.raises(ValueError):
        json_to_tuples('{"fa_pe":')
