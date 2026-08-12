"""Light edge-case tests for Pydantic models (T2 NIT carryforwards).

Scope is intentionally narrow — pin the CURRENT behavior so future model
constraint changes (T2 REVIEWER NIT defer) flag as regressions. This
file does NOT add Field constraints; that is a separate spec.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fincli_api.models import ErrorResponse, ScreenRequest, Stock


def test_stock_serialization_matches_spec_example(sample_stock: Stock) -> None:
    """Round-trip ``model_dump_json -> model_validate`` preserves the wire shape.

    Pins spec §4.3 ``Stock`` example: every field survives a JSON
    round-trip with identical values and types. Catches accidental
    serializer customization (e.g. alias drift) that would break
    polyglot consumers.
    """
    rebuilt = Stock.model_validate_json(sample_stock.model_dump_json())

    assert rebuilt == sample_stock
    # Spot-check the snake_case wire fields (vs. PascalCase Finviz cols)
    # since the snake_case rule is the spec §4.3 normalization contract.
    dumped = rebuilt.model_dump()
    assert "market_cap" in dumped
    assert "finviz_url" in dumped
    assert "rank" in dumped


def test_error_response_rejects_invalid_error_class() -> None:
    """Literal discriminator on ``error_class`` rejects out-of-set values.

    Spec §5.2 fixes the four legal classes (``validation`` / ``upstream``
    / ``parsing`` / ``internal``). The Literal enforces this at parse
    time so a route handler cannot accidentally widen the envelope.
    """
    with pytest.raises(ValidationError):
        ErrorResponse(error_class="not_a_real_class", message="x")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ScreenRequest — filters / scrape_link mutual exclusion + host allowlist.
# ---------------------------------------------------------------------------


def test_screen_request_filters_only_is_valid() -> None:
    """``filters`` alone (no ``scrape_link``) is the existing, still-valid shape."""
    request = ScreenRequest(filters={"fa_pe": "u5"})
    assert request.filters == {"fa_pe": "u5"}
    assert request.scrape_link is None


def test_screen_request_empty_filters_dict_is_valid() -> None:
    """An empty ``filters`` dict is a legal no-filter screen (CONTRACTS §8.2), not
    equivalent to "unset" for the mutual-exclusion check."""
    request = ScreenRequest(filters={})
    assert request.filters == {}


def test_screen_request_scrape_link_only_is_valid() -> None:
    """``scrape_link`` alone (no ``filters``) is the new valid shape."""
    request = ScreenRequest(scrape_link="https://finviz.com/screener.ashx?v=111&f=fa_pe_u5")
    assert request.filters is None
    assert request.scrape_link == "https://finviz.com/screener.ashx?v=111&f=fa_pe_u5"


def test_screen_request_subdomain_scrape_link_is_valid() -> None:
    """A ``finviz.com`` subdomain (e.g. Elite) passes the host allowlist."""
    request = ScreenRequest(scrape_link="https://elite.finviz.com/screener.ashx?v=111")
    assert request.scrape_link == "https://elite.finviz.com/screener.ashx?v=111"


def test_screen_request_both_filters_and_scrape_link_rejected() -> None:
    """Setting both ``filters`` and ``scrape_link`` violates mutual exclusion."""
    with pytest.raises(ValidationError):
        ScreenRequest(filters={"fa_pe": "u5"}, scrape_link="https://finviz.com/screener.ashx")


def test_screen_request_neither_filters_nor_scrape_link_rejected() -> None:
    """Setting neither field violates the "exactly one" contract."""
    with pytest.raises(ValidationError):
        ScreenRequest()


def test_screen_request_non_finviz_host_rejected() -> None:
    """SSRF guard: a non-finviz.com host is rejected even for a valid URL shape."""
    with pytest.raises(ValidationError):
        ScreenRequest(scrape_link="https://evil.example.com/screener.ashx?v=111")


def test_screen_request_non_http_scheme_rejected() -> None:
    """SSRF guard: non-http(s) schemes (e.g. ``file://``) are rejected."""
    with pytest.raises(ValidationError):
        ScreenRequest(scrape_link="file:///etc/passwd")


def test_screen_request_finviz_lookalike_host_rejected() -> None:
    """A host that merely contains ``finviz.com`` (not a real subdomain) is rejected."""
    with pytest.raises(ValidationError):
        ScreenRequest(scrape_link="https://notfinviz.com.evil.example/screener.ashx")


def test_screen_request_finviz_suffix_lookalike_host_rejected() -> None:
    """A host ENDING in the literal ``finviz.com`` without the subdomain dot is rejected.

    Regression pin for the allowlist's dotted-suffix comparison: a future
    slip to ``endswith("finviz.com")`` (dot dropped) would accept this host
    while every other lookalike test still passed.
    """
    with pytest.raises(ValidationError):
        ScreenRequest(scrape_link="https://notfinviz.com/screener.ashx")
