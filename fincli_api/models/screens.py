"""Pydantic request/response models for the ``/screens`` endpoint.

Mirrors the spec in ``docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md``
§4.2 (``ScreenRequest``) and §4.3 (``ScreenResult`` + ``Stock``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Stock(BaseModel):
    """One row from a Finviz screener result, serialized as snake_case JSON.

    Field-naming rule (spec §4.3): snake_case. The verbatim Finviz CSV
    columns (``Ticker``, ``Market Cap``, ``P/E``, ``No.``) are normalized
    to ``ticker``, ``market_cap``, ``pe``, and ``rank`` respectively.

    Numeric vs. string preservation: numeric for already-coerced values
    (``market_cap`` is converted via ``fincli/utils/market_cap.py``), and
    string for fincli-formatted values that carry units / currency /
    percent signs (``pe``, ``price``, ``change``, ``volume``). Consumers
    opt in to parsing those.

    ``finviz_url`` reuses fincli's existing URL builder
    ``StockTableScreenerParser.ticker_link()`` in
    ``fincli/stock_screening/parsers/stock_table.py`` (concatenates
    ``BASE_URL`` from ``fincli/resource/params/const.py`` with the per-row
    href). That same value lands in the DataFrame's ``Link`` column and is
    what the CLI wraps in an Excel ``=HYPERLINK(...)`` formula on the CSV
    write path (then dropped). The T3 adapter is the bridge that calls
    into fincli to populate this field.
    """

    ticker: str
    company: str
    sector: str
    industry: str
    country: str
    market_cap: float | None
    pe: str | None
    price: str
    change: str
    volume: str
    rank: int
    finviz_url: str


class ScreenRequest(BaseModel):
    """Request body for ``POST /screens`` (spec §4.2)."""

    filters: dict[str, str] = Field(
        ...,
        examples=[{"fa_pe": "u5", "sec": "energy"}],
        description=(
            "Map of Finviz filter key to value code. See ``GET /filters`` for the valid set."
        ),
    )


class ScreenResult(BaseModel):
    """Response body for ``POST /screens`` on success (spec §4.3).

    Mirrors fincli's ``--json-summary`` schema (CONTRACTS §5.5) plus the
    ``stocks`` array. ``schema_version`` bumps independently from the
    API release version per CONTRACTS §7.

    ``started_at`` / ``finished_at`` are ISO 8601 strings (e.g.
    ``"2026-05-22T15:23:01.234Z"``) rather than ``datetime`` for
    byte-equivalence with what fincli's ``--json-summary`` already
    emits. Tightening to ``datetime`` would change the JSON shape and
    therefore requires a ``schema_version`` bump.
    """

    schema_version: int = 1
    row_count: int
    duration_ms: int
    started_at: str
    finished_at: str
    stocks: list[Stock]
