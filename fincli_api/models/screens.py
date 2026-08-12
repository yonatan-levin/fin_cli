"""Pydantic request/response models for the ``/screens`` endpoint.

Mirrors the spec in ``docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md``
§4.2 (``ScreenRequest``) and §4.3 (``ScreenResult`` + ``Stock``).
"""

from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


# Hosts allowed on the `scrape_link` field: `finviz.com` itself and any of its
# subdomains (e.g. `elite.finviz.com`). The API binds `0.0.0.0` by default
# (INTEGRATION.md), so an unrestricted URL fetch on this field would be an
# SSRF hole — a caller could point `scrape_link` at an internal service and
# have the server fetch it. This allowlist is a DELIBERATE deviation from
# raw CLI `--scrape-link` parity (which accepts any URL, since it's a local,
# single-user process) — see INTEGRATION.md "Host allowlist" note.
_ALLOWED_SCRAPE_LINK_HOST = "finviz.com"
_ALLOWED_SCRAPE_LINK_HOST_SUFFIX = f".{_ALLOWED_SCRAPE_LINK_HOST}"


def _validate_scrape_link(url: str) -> None:
    """Reject any ``scrape_link`` that is not an http(s) finviz.com URL.

    Raises:
        ValueError: If the scheme is not ``http``/``https``, or the host is
            not exactly ``finviz.com`` or a subdomain of it. Pydantic wraps
            this into a standard 422 request-validation error (see
            ``ScreenRequest`` docstring for why that envelope, not
            ``ErrorResponse``, is correct here).
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise ValueError(f"scrape_link must use http or https, got {parts.scheme!r}.")
    host = parts.hostname
    if host is None or not (
        host == _ALLOWED_SCRAPE_LINK_HOST or host.endswith(_ALLOWED_SCRAPE_LINK_HOST_SUFFIX)
    ):
        raise ValueError(
            f"scrape_link host {host!r} is not allowed; only {_ALLOWED_SCRAPE_LINK_HOST} "
            "and its subdomains are permitted (SSRF guard)."
        )


class ScreenRequest(BaseModel):
    """Request body for ``POST /screens`` (spec §4.2).

    Exactly one of ``filters`` or ``scrape_link`` must be set — the two
    input modes mirror the CLI's mutually-exclusive ``--filter`` /
    ``--filters-json`` / ``--filters-file`` vs. ``--scrape-link`` input
    modes (CONTRACTS §1). Violating the mutual-exclusion rule (both set,
    or neither set) raises a standard Pydantic ``ValueError`` at request
    parse time, which FastAPI surfaces as its normal 422
    request-validation envelope — NOT the ``ErrorResponse`` envelope used
    for pipeline failures (``fincli_api/exception_handlers.py``). That
    distinction is deliberate: this is a malformed *request*, not a failed
    *screen run*, so it belongs to FastAPI's own validation-error shape.

    ``scrape_link`` additionally requires an absolute ``http``/``https``
    URL whose host is ``finviz.com`` or a subdomain of it (SSRF guard —
    see ``_validate_scrape_link``); this is enforced the same way, via the
    same 422 envelope.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"filters": {"fa_pe": "u5", "sec": "energy"}},
                {
                    "scrape_link": (
                        "https://finviz.com/screener.ashx?v=111"
                        "&f=fa_sales3years_pos,ta_perf2_3yup&ft=2"
                    )
                },
            ]
        }
    )

    filters: dict[str, str] | None = Field(
        default=None,
        examples=[{"fa_pe": "u5", "sec": "energy"}],
        description=(
            "Map of Finviz filter key to value code. See ``GET /filters`` for the valid set. "
            "Mutually exclusive with ``scrape_link`` — exactly one of the two must be set."
        ),
    )
    scrape_link: str | None = Field(
        default=None,
        examples=["https://finviz.com/screener.ashx?v=111&f=fa_sales3years_pos,ta_perf2_3yup"],
        description=(
            "Direct Finviz screener URL, fetched verbatim with NO filter-inventory "
            "validation (mirrors the CLI's --scrape-link). Mutually exclusive with "
            "``filters``. Restricted to finviz.com and its subdomains over http(s) — a "
            "deliberate deviation from CLI parity to close an SSRF hole, since the API "
            "binds 0.0.0.0 by default. See INTEGRATION.md."
        ),
    )

    @model_validator(mode="after")
    def _check_exactly_one_input_mode(self) -> ScreenRequest:
        """Enforce ``filters`` XOR ``scrape_link`` and the scrape_link host allowlist.

        Uses ``is None`` (not truthiness) so an explicit empty ``filters``
        dict (``{}`` — a legal no-filter screen per CONTRACTS §8.2) still
        counts as "filters was set".
        """
        if (self.filters is None) == (self.scrape_link is None):
            raise ValueError(
                "Exactly one of `filters` or `scrape_link` must be provided "
                "(mutually exclusive) — see ScreenRequest docstring."
            )
        if self.scrape_link is not None:
            _validate_scrape_link(self.scrape_link)
        return self


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
