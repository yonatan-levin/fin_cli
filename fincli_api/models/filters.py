"""Pydantic models for the ``GET /filters`` endpoint.

Mirrors the JSON shape emitted by ``fincli --list-filters --json`` so the
CLI and HTTP transports stay byte-equivalent (modulo HTTP framing). Both
paths ultimately call
``fincli.resource.params.validators.list_valid_filters_with_labels`` —
see CONTRACTS.md §5.6 and ``docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`` §4.4.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FilterEntry(BaseModel):
    """One filter's metadata: human label plus value-code to value-label map.

    Mirrors the per-entry shape in CONTRACTS §5.6 / spec §4.4. The empty
    string value code (the Finviz "Any" sentinel) is a legal map key — the
    validator accepts it — so consumers must not filter it out blindly.

    Attributes:
        label: Human-readable label for the filter key, derived mechanically
            from the underlying Python attribute name (acronyms preserved;
            connector words lowercased). Starting point only — UI consumers
            may override locally for polish.
        values: ``{value_code: value_label}`` map for the filter's legal
            values. Iteration order in the wire JSON follows Python dict
            insertion order, which mirrors the source params-class
            declaration order.
    """

    label: str
    values: dict[str, str]


class FilterInventory(BaseModel):
    """Full filter inventory response for ``GET /filters``.

    Byte-equivalent (modulo HTTP framing) to ``fincli --list-filters --json``
    output — both paths consume ``list_valid_filters_with_labels`` via
    different transports (CLI vs. HTTP). See spec §4.4 and CONTRACTS §5.6.

    Attributes:
        schema_version: Contract version per CONTRACTS §7. Pinned to ``1``;
            bumps independently from the release version and only on
            breaking schema changes (field removed/renamed or semantics
            changed). Additive changes do not bump.
        keys: Canonical filter-key ordering (Fundamental -> Descriptive ->
            Technical). Polyglot consumers iterate this list to lock
            iteration order — Go's ``encoding/json`` randomizes map
            iteration and JS object iteration is engine-defined, so the
            ``filters`` dict alone is not a stable ordering contract.
        filters: ``{query_key: FilterEntry}`` map keyed by Finviz query key
            (not the Python attribute name).
    """

    schema_version: int = 1
    keys: list[str] = Field(
        ...,
        description=(
            "Canonical filter-key ordering (Fundamental -> Descriptive -> "
            "Technical). Polyglot consumers iterate this list to lock "
            "iteration order (Go's encoding/json randomizes map iteration)."
        ),
    )
    filters: dict[str, FilterEntry]
