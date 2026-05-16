"""Strict dict-only JSON-to-tuples converter for Finviz filter input.

Schema lockdown landed in `docs/features/archive/pipeline-mode-spec.md` §5.1 step 3
(OQ1 resolution): the canonical filter shape across the system is a flat
JSON object whose keys are Finviz query_keys and whose values are
value_codes — both strings. The legacy converter accepted both list-of-pairs
and dict shapes and silently ignored bad inputs via `print` calls; that made
malformed input look like "no filters" and produced silent-corruption runs.

This module raises `ValueError` for every non-canonical shape so the CLI can
translate the error into a `click.UsageError` (exit 2) instead of swallowing
the mistake. `filter_history.json` (CONTRACTS §4.3) already uses this same
flat-object shape — one schema across the system.

Empty dict (`{}`) is allowed and represents the no-filters case; upstream
code treats an empty tuple as "fall through to interactive selection".
"""

from __future__ import annotations

import json

# Keep error messages stable so CLI tests can assert on substrings without
# coupling to wording. The leading word ("object" / "string") is the contract.
# Use literal % formatting so the example JSON braces in the message do not
# collide with `str.format` field syntax.
_NOT_OBJECT_MSG = 'filters JSON must be a flat object (e.g. \'{"fa_pe":"u20"}\'); got %s'
_BAD_VALUE_MSG = 'filters JSON values must be strings (e.g. \'{"fa_pe":"u20"}\'); key %r maps to %s'


def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]:
    """Parse a flat-object JSON string into a tuple of `(key, value)` pairs.

    Args:
        filters_json: A JSON document literal, e.g. ``'{"fa_pe":"u20"}'``.
            Single quotes are normalized to double quotes for shell-friendly
            usage (preserves the historic convenience).

    Returns:
        A tuple of ``(key, value)`` string pairs in insertion order. The
        empty tuple is returned for ``"{}"`` (the no-filters case).

    Raises:
        ValueError: If the JSON is malformed, the top-level shape is not an
            object, or any value is not a string. The CLI translates this
            into ``click.UsageError`` (exit 2).
    """
    # Normalize single quotes so shells that strip double quotes still work.
    # JSON string contents that legitimately contain single quotes would be
    # corrupted by this — out of scope for filter codes (all ASCII, no quotes).
    normalized = filters_json.replace("'", '"')

    # `json.loads` raises `json.JSONDecodeError`, which is a `ValueError`
    # subclass — so the "raises ValueError" contract is satisfied without an
    # explicit re-raise.
    data = json.loads(normalized)

    if not isinstance(data, dict):
        # Distinguish list/array from scalar in the message — list is the
        # most likely legacy mistake to surface helpfully.
        kind = "list" if isinstance(data, list) else type(data).__name__
        raise ValueError(_NOT_OBJECT_MSG % kind)

    # Flat-object check: every value must be a string. Catches nested objects,
    # arrays, numbers, booleans, and null.
    for key, value in data.items():
        if not isinstance(value, str):
            raise ValueError(_BAD_VALUE_MSG % (key, type(value).__name__))

    # `dict` items in Python 3.7+ preserve insertion order, so the output
    # tuple matches the JSON document order.
    return tuple(data.items())
