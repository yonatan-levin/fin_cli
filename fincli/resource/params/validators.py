"""Strict validation for structured Finviz filter input.

Carved out as the single chokepoint that closes the silent-drop hazard at
`fincli/utils/quary_builders.py:18-22`: the legacy query builder iterates
the param classes and silently skips any unknown key, so a typo in a
non-interactive flag like `--filter sec=enrgy` produced an empty filter
URL and no warning. With structured input (`--filter`, `--filters-json`,
`--filters-file`) landing in `docs/features/archive/pipeline-mode-spec.md` Pillar 1,
every typo would otherwise become a wasted scrape; this module raises a
``click.UsageError`` so the CLI exits 2 with a clear message instead.

Design notes:

  - Single chokepoint: `core.configuration.configurator.build_config` calls
    `validate_filter_pairs` immediately after `json_to_tuples`. The early-
    return path in `select_filters_and_values` does not need its own call —
    everything reaches the configurator first.
  - `--scrape-link` and `--history` deliberately skip validation (URL is
    opaque; history was previously valid by construction).
  - Interactive picker UI does its own bounds-checked input, so it does not
    need this validator either.
  - `list_valid_filters()` exposes the same inventory the validator walks;
    it powers the inline error-message suggestions and a future
    `--help-filters` CLI flag (deferred — see spec §9 / §7.2 note).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TypedDict

import click

from ._label_format import attr_to_label
from .descriptive_params import Descriptive_Params
from .fundamental_params import Fundamental_Params
from .technical_params import Technical_Params


class _LabelledEntry(TypedDict):
    """Per-entry shape returned by ``list_valid_filters_with_labels``.

    Pinning the shape as a TypedDict (rather than ``dict[str, object]``)
    lets call sites read ``entry["values"]`` without an ``isinstance``
    re-narrow — the type checker already knows it is a ``dict[str, str]``.
    Folded in per REVIEWER LOW #1 on the T1 commit.
    """

    label: str
    values: dict[str, str]


# The three classes whose `[query_key, {value_code: display_name}]` attributes
# define the universe of legal filter pairs. Centralized as a module constant
# so a future fourth params file is a one-line edit.
_PARAM_CLASSES: tuple[type, ...] = (
    Fundamental_Params,
    Descriptive_Params,
    Technical_Params,
)

# Cap the inline error-message suggestion list so messages stay scannable.
# The full inventory is still available via `list_valid_filters()` (and a
# future `--help-filters` flag).
_MAX_SUGGESTIONS: int = 10


def _iter_param_entries() -> Iterator[tuple[str, str, dict[str, str]]]:
    """Yield ``(attr_name, query_key, values_dict)`` for every legal entry.

    Single source of truth for walking the registered param classes. Both
    `list_valid_filters` and `list_valid_filters_with_labels` consume this
    so the param-class introspection rules (skip dunders, require
    2-element list shape, require ``[str, dict]`` types) live in one place.

    Filter entries on each class are conventionally ``UPPER_SNAKE_CASE``
    attribute names bound to ``[query_key, {value_code: display_name}]``
    lists. Anything that does not match that shape (helper methods,
    nested classes, metadata constants) is silently skipped — same
    behavior the original inline walker had.

    Yields:
        ``(attr_name, query_key, values_dict)`` triples in param-class
        declaration order (Fundamental, then Descriptive, then Technical),
        with each class's entries in source-file declaration order.
    """
    for cls in _PARAM_CLASSES:
        for attr_name, attr_value in vars(cls).items():
            if attr_name.startswith("__"):
                continue
            # Param attributes are 2-element lists: [query_key, values_dict].
            if not isinstance(attr_value, list) or len(attr_value) != 2:
                continue
            query_key, values_dict = attr_value
            if not isinstance(query_key, str) or not isinstance(values_dict, dict):
                continue
            # Cast keys to str defensively — every legitimate registry entry
            # already uses string keys, but this keeps mypy strict happy.
            normalized_values: dict[str, str] = {
                str(code): str(label) for code, label in values_dict.items()
            }
            yield attr_name, query_key, normalized_values


def list_valid_filters() -> dict[str, list[str]]:
    """Return the full ``{query_key: [value_code, ...]}`` inventory.

    Walks every `[query_key, {value_code: display_name}]` attribute on each
    of the registered params classes via `_iter_param_entries`. Used by
    `validate_filter_pairs` to build error-message suggestions and by the
    future `--help-filters` flag.

    Returns:
        A mapping from each registered Finviz query key to the list of
        valid value codes for that key. Insertion order matches the param
        class declaration order (Fundamental, then Descriptive, then
        Technical). Drops the value labels — use
        ``list_valid_filters_with_labels()`` if labels are needed.
    """
    return {
        query_key: list(values_dict) for _attr_name, query_key, values_dict in _iter_param_entries()
    }


def list_valid_filters_with_labels() -> dict[str, _LabelledEntry]:
    """Return the inventory with human labels + value-label maps per spec §5.2.

    Sibling of `list_valid_filters`: same source data (walks
    `_iter_param_entries`) but preserves the value labels and adds a
    derived key label (via `attr_to_label`) instead of dropping them.

    Used by ``fincli --list-filters --json`` to dump the inventory as JSON
    for non-Python consumers (Go, Node, etc.) per
    `docs/features/list-filters-spec.md` §5.4.

    Per-entry shape (`_LabelledEntry`):
    ``{"label": str, "values": {value_code: value_label}}``. The empty-string
    value code (the "Any" sentinel) is preserved verbatim because the
    validator accepts it as a legal value.

    Returns:
        A mapping ``{query_key: {"label": ..., "values": {...}}}`` whose
        insertion order matches param-class declaration order (Fundamental,
        then Descriptive, then Technical).
    """
    inventory: dict[str, _LabelledEntry] = {}
    for attr_name, query_key, values_dict in _iter_param_entries():
        inventory[query_key] = {
            "label": attr_to_label(attr_name),
            "values": dict(values_dict),
        }
    return inventory


def validate_filter_pairs(pairs: tuple[tuple[str, str], ...]) -> None:
    """Raise `click.UsageError` if any pair has an unknown key or value.

    Args:
        pairs: A tuple of ``(query_key, value_code)`` pairs as produced by
            ``core.converters.json.json_to_tuples``.

    Raises:
        click.UsageError: When any key is not registered, or when a known
            key is paired with an unregistered value code. The error message
            names the offending token and lists up to ``_MAX_SUGGESTIONS``
            valid alternatives so the user can self-correct.
    """
    # Build the inventory once so a multi-pair input only walks the param
    # classes a single time. The dict is small enough that the cost is
    # negligible even on the no-failure happy path.
    inventory = list_valid_filters()
    valid_keys = list(inventory.keys())

    for key, value in pairs:
        if key not in inventory:
            suggestions = ", ".join(valid_keys[:_MAX_SUGGESTIONS])
            raise click.UsageError(
                f"Unknown filter key {key!r}. Valid keys include: {suggestions}. "
                f"See fincli/resource/params/ for the full filter inventory."
            )

        valid_values = inventory[key]
        if value not in valid_values:
            value_suggestions = ", ".join(valid_values[:_MAX_SUGGESTIONS])
            raise click.UsageError(
                f"Unknown value {value!r} for filter key {key!r}. "
                f"Valid values include: {value_suggestions}. "
                f"See fincli/resource/params/ for the full filter inventory."
            )
