"""End-to-end tests for ``fincli --list-filters --json`` (list-filters-spec).

Subprocesses ``python -m fincli --list-filters --json`` (matching the
``tests/integration/test_pipeline_*.py`` convention — uses the module form
rather than the entry-point shim so the test does not depend on the script
being on ``PATH`` in CI) and asserts the full §7.3 (schema) + §7.4 (content
sampling) acceptance bullets from ``docs/features/list-filters-spec.md``.

This is the polyglot-consumer contract test: every assertion below is the
exact shape a Go / Node integrator's decoder would lock against.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator

import pytest


@pytest.fixture(scope="module")
def inventory_payload() -> Iterator[dict[str, object]]:
    """Run the CLI once per module and reuse the parsed payload.

    The subprocess fork is the slow part (~250ms on a warm Python); reusing
    the payload across the six assertions in this file keeps the suite snappy
    without sacrificing the end-to-end-via-stdout contract test.
    """
    result = subprocess.run(
        [sys.executable, "-m", "fincli", "--list-filters", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"--list-filters --json should exit 0; got {result.returncode}. stderr={result.stderr!r}"
    )
    # Spec §7.3 bullet 1: stdout is exactly one JSON line.
    # json.loads on the stripped output validates "parseable as one shot".
    yield json.loads(result.stdout.strip())


# ---------------------------------------------------------------------------
# §7.3 — JSON schema bullets (all 8, amended +4 per deep-think for `keys`).
# ---------------------------------------------------------------------------


def test_stdout_is_single_json_line_with_trailing_newline() -> None:
    """Stdout = exactly one JSON object on a single line + trailing newline.

    Pins spec §7.3 bullet 1. This is the only test in the file that does its
    own subprocess invocation (rather than using the cached fixture) because
    the assertion is about the raw stdout shape, not the parsed payload.
    """
    result = subprocess.run(
        [sys.executable, "-m", "fincli", "--list-filters", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

    # The trailing newline comes from `click.echo`; everything before it is
    # one JSON line. Splitting on newlines and dropping the trailing empty
    # string must leave exactly one non-empty element.
    lines = result.stdout.split("\n")
    assert lines[-1] == "", "Expected trailing newline from click.echo"
    non_empty = [line for line in lines if line]
    assert len(non_empty) == 1, (
        f"Expected exactly one JSON line on stdout; got {len(non_empty)} lines: {non_empty!r}"
    )
    # And the single line is valid JSON (no pretty-printing splitters).
    json.loads(non_empty[0])


def test_top_level_keys_exact_set(inventory_payload: dict[str, object]) -> None:
    """Top-level keys are exactly ``{"schema_version", "keys", "filters"}``.

    Pins spec §7.3 bullet 2. Extra keys would silently expand the contract
    (Go consumers' decoders ignore unknown fields); a missing key would
    break them. This assertion is the wire-shape lock.
    """
    assert set(inventory_payload.keys()) == {"schema_version", "keys", "filters"}, (
        f"Expected exactly schema_version/keys/filters; got {sorted(inventory_payload.keys())!r}"
    )


def test_schema_version_is_one(inventory_payload: dict[str, object]) -> None:
    """``schema_version == 1``. Pins spec §7.3 bullet 3."""
    assert inventory_payload["schema_version"] == 1


def test_keys_is_nonempty_list_of_strings(
    inventory_payload: dict[str, object],
) -> None:
    """``keys`` is a non-empty list of strings. Pins spec §7.3 bullet 4."""
    keys = inventory_payload["keys"]
    assert isinstance(keys, list), f"keys is {type(keys)}, expected list"
    assert keys, "keys list is empty"
    for k in keys:
        assert isinstance(k, str), f"non-string key in keys: {k!r} ({type(k)})"


def test_keys_membership_and_uniqueness_match_filters(
    inventory_payload: dict[str, object],
) -> None:
    """``set(keys) == set(filters.keys())`` and ``len(keys) == len(filters)``.

    Pins spec §7.3 bullets 5+6: every advertised key has a filter entry
    (no orphans), every filter entry is advertised (no missing), and the
    keys list has no duplicates. The combined membership-and-length check
    is the polyglot-consumer safety net.
    """
    keys = inventory_payload["keys"]
    filters = inventory_payload["filters"]
    assert isinstance(keys, list)
    assert isinstance(filters, dict)
    assert set(keys) == set(filters.keys()), (
        f"keys vs filters membership diverged. "
        f"keys - filters = {set(keys) - set(filters.keys())!r}; "
        f"filters - keys = {set(filters.keys()) - set(keys)!r}"
    )
    assert len(keys) == len(filters), (
        f"keys has duplicates: len(keys)={len(keys)}, len(filters)={len(filters)}"
    )


def test_keys_order_matches_param_class_declaration_sequence(
    inventory_payload: dict[str, object],
) -> None:
    """``keys`` order = Fundamental → Descriptive → Technical.

    Pins spec §7.3 bullet 7 (the canonical-ordering contract polyglot
    consumers iterate ``keys`` against). A regression that re-orders the
    walker would silently break Go consumers that materialize dropdowns
    in this order.
    """
    keys = inventory_payload["keys"]
    assert isinstance(keys, list)

    # Spot-check one well-known representative from each param class.
    fa_pe_idx = keys.index("fa_pe")  # Fundamental
    sec_idx = keys.index("sec")  # Descriptive
    ta_rsi_idx = keys.index("ta_rsi")  # Technical

    assert fa_pe_idx < sec_idx, (
        f"Fundamental ('fa_pe' at {fa_pe_idx}) must precede Descriptive ('sec' at {sec_idx})"
    )
    assert sec_idx < ta_rsi_idx, (
        f"Descriptive ('sec' at {sec_idx}) must precede Technical ('ta_rsi' at {ta_rsi_idx})"
    )


def test_every_filter_entry_has_exact_label_values_keys(
    inventory_payload: dict[str, object],
) -> None:
    """Every ``filters[k]`` is a dict with exactly ``{"label", "values"}``.

    Pins spec §7.3 bullets 8-9 + 10 (per-entry shape, non-empty label,
    str-to-str values map). Walks the entire inventory so a single rogue
    entry fails loudly.
    """
    filters = inventory_payload["filters"]
    assert isinstance(filters, dict)
    assert filters, "filters dict is empty"

    for key, entry in filters.items():
        assert isinstance(entry, dict), f"{key} entry is {type(entry)}"
        assert set(entry.keys()) == {"label", "values"}, (
            f"{key} entry has keys {sorted(entry.keys())!r}, expected {{'label', 'values'}}"
        )
        label = entry["label"]
        values = entry["values"]
        assert isinstance(label, str) and label, f"{key}.label is empty or non-str: {label!r}"
        assert isinstance(values, dict) and values, f"{key}.values is empty or non-dict: {values!r}"
        for code, value_label in values.items():
            assert isinstance(code, str), f"{key}.values has non-str code {code!r}"
            assert isinstance(value_label, str), (
                f"{key}.values[{code!r}] is non-str: {value_label!r}"
            )


# ---------------------------------------------------------------------------
# §7.4 — Content sampling (all 7 bullets).
# ---------------------------------------------------------------------------


def test_content_sampling_matches_spec_examples(
    inventory_payload: dict[str, object],
) -> None:
    """Spot-check the §7.4 content bullets against the live inventory.

    Pins every §7.4 bullet in one focused test:
      - filters["fa_pe"].label == "PE"
      - filters["fa_pe"].values[""] == "Any"
      - filters["fa_pe"].values["u20"] == "Under 20"
      - filters["sec"].label == "Sector"
      - filters["sec"].values["basicmaterials"] == "Basic Materials"
      - filters["ta_rsi"].label == "RSI 14"
      - at least one filter from each of the three param classes is present
        (covered by the fa_pe / sec / ta_rsi keys being present).
    """
    filters = inventory_payload["filters"]
    assert isinstance(filters, dict)

    fa_pe = filters["fa_pe"]
    assert isinstance(fa_pe, dict)
    assert fa_pe["label"] == "PE"
    fa_pe_values = fa_pe["values"]
    assert isinstance(fa_pe_values, dict)
    assert fa_pe_values[""] == "Any"
    assert fa_pe_values["u20"] == "Under 20"

    sec = filters["sec"]
    assert isinstance(sec, dict)
    assert sec["label"] == "Sector"
    sec_values = sec["values"]
    assert isinstance(sec_values, dict)
    assert sec_values["basicmaterials"] == "Basic Materials"

    ta_rsi = filters["ta_rsi"]
    assert isinstance(ta_rsi, dict)
    assert ta_rsi["label"] == "RSI 14"
