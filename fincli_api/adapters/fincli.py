"""Boundary layer between ``fincli_api`` and the existing ``fincli`` package.

This module is the **only** file in ``fincli_api/`` allowed to import from
``fincli/`` (architectural rule per spec
``docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`` §3.2). The two
exported functions bridge the Pydantic API models to fincli's existing
synchronous screener pipeline:

  * ``get_filter_inventory()`` — wraps
    ``fincli.resource.params.validators.list_valid_filters_with_labels``
    into the ``FilterInventory`` shape for ``GET /filters``. Byte-equivalent
    (modulo HTTP framing) to ``fincli --list-filters --json`` because both
    transports call the same Python function (CONTRACTS §5.6).

  * ``run_screen(filters)`` — wraps
    ``fincli.app.main.screen_to_dataframe`` and projects the resulting
    DataFrame rows into the ``ScreenResult`` / ``Stock`` shapes for
    ``POST /screens``. Captures wall-clock timing for the per-run
    metadata fields (``duration_ms`` / ``started_at`` / ``finished_at``)
    per spec §4.3.

Exceptions raised by ``fincli`` (validation, upstream, parsing, internal)
propagate up unchanged — the T4d FastAPI exception handler classifies them
via ``fincli.app.exit_codes.classify`` and maps them onto the
``ErrorResponse`` envelope + HTTP status (spec §5).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# pandas ships no inline type stubs and there is no project-wide mypy
# override for it; the legacy fincli modules already eat the same
# ``import-untyped`` error at baseline. Silence it locally so the new
# adapter file passes ``mypy fincli_api`` cleanly without touching the
# shared pyproject overrides (out of scope for this task).
import pandas as pd  # type: ignore[import-untyped]

from fincli.app.main import screen_to_dataframe
from fincli.resource.params.const import BASE_URL
from fincli.resource.params.validators import list_valid_filters_with_labels
from fincli_api.models import FilterEntry, FilterInventory, ScreenResult, Stock

# Suffix appended to ``BASE_URL`` to construct the canonical Finviz quote
# URL per spec §4.3 example shape (``https://finviz.com/quote.ashx?t={TICKER}``).
# Note: the CSV path's ``StockTableScreenerParser.ticker_link`` actually
# emits ``https://finviz.com//quote.ashx?t={TICKER}`` (double slash —
# ``BASE_URL`` ends with ``/`` and the parsed href starts with ``/``).
# Finviz tolerates the double slash so it still works in the Excel
# ``=HYPERLINK(...)`` formula on the CSV write path, but the API
# normalizes to the spec's single-slash form. Tracking the legacy
# double-slash quirk as a low-priority pre-existing fincli cosmetic
# bug, out of T3 scope.
_FINVIZ_QUOTE_PATH = "quote.ashx?t="

# ISO 8601 "Z" suffix replacement for the ``+00:00`` offset that
# ``datetime.isoformat()`` emits for UTC-aware timestamps. Spec §4.3
# example uses the Z form (``"2026-05-22T15:23:01.234Z"``).
_UTC_OFFSET_SUFFIX = "+00:00"
_UTC_Z_SUFFIX = "Z"


def get_filter_inventory() -> FilterInventory:
    """Return the full filter inventory for ``GET /filters``.

    Thin wrapper over
    ``fincli.resource.params.validators.list_valid_filters_with_labels``
    that lifts the returned dict into the ``FilterInventory`` Pydantic
    model. Both this function and the CLI's ``--list-filters --json``
    consume the same underlying function — they cannot drift.

    Returns:
        ``FilterInventory`` with ``schema_version=1``, the canonical
        ordering ``keys`` list (Fundamental -> Descriptive -> Technical),
        and the ``filters`` map of ``{query_key: FilterEntry}``.

    Raises:
        Propagates any exception from
        ``list_valid_filters_with_labels``; the T4d handler classifies
        such failures as ``internal`` (HTTP 500).
    """
    inventory = list_valid_filters_with_labels()
    # ``dict.keys()`` preserves insertion order on Python 3.7+, so the
    # ``keys`` list mirrors the param-class declaration order (spec §4.4
    # canonical ordering requirement).
    keys = list(inventory.keys())
    filters = {
        query_key: FilterEntry(label=entry["label"], values=entry["values"])
        for query_key, entry in inventory.items()
    }
    return FilterInventory(schema_version=1, keys=keys, filters=filters)


def run_screen(filters: dict[str, str]) -> ScreenResult:
    """Run a Finviz screen and return the parsed rows as ``ScreenResult``.

    Bridges ``fincli.app.main.screen_to_dataframe`` to the API contract.
    Times the call in UTC so the metadata fields are pipeline-friendly
    (ISO 8601 with ``Z`` suffix per spec §4.3). No CSV is ever written —
    the DataFrame stays in memory.

    Args:
        filters: ``{query_key: value_code}`` map matching the
            ``ScreenRequest.filters`` wire format. Callers (the T4b route
            handler) are responsible for validating shape before calling.

    Returns:
        ``ScreenResult`` with ``schema_version=1``, the per-run timing
        metadata, and the ``stocks`` list. The list is empty when Finviz
        returned zero rows for the filter set (still a 200 success per
        spec §5.1).

    Raises:
        Propagates any exception from the screener pipeline (validation,
        upstream, parsing, internal). The T4d handler maps them onto the
        ``ErrorResponse`` envelope via ``fincli.app.exit_codes.classify``.
    """
    started_at = datetime.now(tz=UTC)

    # ``hyperlink_wrap=False`` keeps the ``Ticker`` column as the raw
    # symbol (e.g. ``"AAPL"``) rather than the Excel ``=HYPERLINK(...)``
    # formula the CLI's file-write path uses. API consumers want bare
    # tickers — spec §4.3 ``Stock.ticker`` example is ``"CNX"``.
    df = screen_to_dataframe(filters, hyperlink_wrap=False)

    # ``Link`` column is dropped inside ``build_data_frame``, so the
    # adapter rebuilds the canonical Finviz quote URL per row matching
    # spec §4.3; see ``_FINVIZ_QUOTE_PATH`` above for the CSV-path drift.
    stocks = [_row_to_stock(row) for _, row in df.iterrows()]

    finished_at = datetime.now(tz=UTC)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)

    return ScreenResult(
        schema_version=1,
        row_count=len(stocks),
        duration_ms=duration_ms,
        started_at=_iso_z(started_at),
        finished_at=_iso_z(finished_at),
        stocks=stocks,
    )


def _row_to_stock(row: pd.Series) -> Stock:
    """Project one DataFrame row into a ``Stock`` Pydantic instance.

    Column-to-field mapping per spec §4.3 (Finviz column name -> Stock
    snake_case field):

      * ``No.``          -> ``rank`` (cast str -> int; Finviz cell is a
        digit string from ``get_text(strip=True)``)
      * ``Ticker``       -> ``ticker``
      * ``Company``      -> ``company``
      * ``Sector``       -> ``sector``
      * ``Industry``     -> ``industry``
      * ``Country``      -> ``country``
      * ``Market Cap``   -> ``market_cap`` (nullable ``Float64`` coerced
        by ``convert_market_cap_to_numeric`` upstream; ``pd.NA`` is
        normalized to ``None`` because Pydantic strict mode rejects it)
      * ``P/E``          -> ``pe`` (string preserved verbatim; Finviz
        emits ``"-"`` for "no value" — the API surfaces it as-is so
        consumers can branch on the literal)
      * ``Price``        -> ``price``
      * ``Change``       -> ``change``
      * ``Volume``       -> ``volume``

    The DataFrame omits a ``Link`` column at this stage (dropped inside
    ``build_data_frame``), so ``finviz_url`` is reconstructed from the
    ticker via ``BASE_URL + "quote.ashx?t={ticker}"`` — produces the
    spec §4.3 single-slash URL. See the module-level comment on
    ``_FINVIZ_QUOTE_PATH`` for why this is normalized rather than
    byte-equivalent to the CSV path's ``ticker_link``.

    Args:
        row: One row from the DataFrame returned by
            ``screen_to_dataframe(filters, hyperlink_wrap=False)``.

    Returns:
        A validated ``Stock`` instance.
    """
    ticker = str(row["Ticker"])
    return Stock(
        ticker=ticker,
        company=str(row["Company"]),
        sector=str(row["Sector"]),
        industry=str(row["Industry"]),
        country=str(row["Country"]),
        market_cap=_nullable_float(row["Market Cap"]),
        pe=_nullable_str(row["P/E"]),
        price=str(row["Price"]),
        change=str(row["Change"]),
        volume=str(row["Volume"]),
        rank=int(row["No."]),
        finviz_url=f"{BASE_URL}{_FINVIZ_QUOTE_PATH}{ticker}",
    )


def _nullable_float(value: Any) -> float | None:
    """Coerce a pandas nullable ``Float64`` cell to ``float | None``.

    ``convert_market_cap_to_numeric`` upstream emits ``pd.NA`` for
    unparseable Finviz cells, and Pydantic strict mode rejects ``pd.NA``
    (it is neither ``None`` nor ``float``). ``pd.isna`` handles
    ``pd.NA``, ``numpy.nan``, and ``None`` uniformly.
    """
    if pd.isna(value):
        return None
    return float(value)


def _nullable_str(value: Any) -> str | None:
    """Coerce a possibly-missing string cell to ``str | None``.

    Finviz's ``P/E`` column may render as ``"-"`` or empty — both are
    legitimate "no value" markers. ``pd.isna`` catches the pandas-NA
    case; the literal string is preserved so consumers can branch on
    Finviz's own sentinel without re-implementing the heuristic.
    """
    if pd.isna(value):
        return None
    return str(value)


def _iso_z(moment: datetime) -> str:
    """Format a UTC-aware ``datetime`` as ISO 8601 with the ``Z`` suffix.

    ``datetime.isoformat()`` emits ``"...+00:00"`` for UTC-aware
    instants; the spec §4.3 example uses the trailing ``Z`` form
    (``"2026-05-22T15:23:01.234Z"``). Single chokepoint so both
    ``started_at`` and ``finished_at`` share one format rule.
    """
    return moment.isoformat().replace(_UTC_OFFSET_SUFFIX, _UTC_Z_SUFFIX)
