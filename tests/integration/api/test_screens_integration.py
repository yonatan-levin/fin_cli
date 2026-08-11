"""POST /screens integration — real fincli pipeline + mocked Finviz HTML.

Each test drives the route handler through the real ``run_screen`` adapter,
real ``screen_to_dataframe`` orchestrator, real BS4 parsers, and real
``validate_filter_pairs`` gate. Only ``fincli.app.main.fetch_page_sync``
is mocked (see ``conftest.py`` ``mock_fetch`` fixture rationale).

Coverage targets one canned HTML fixture per failure / success branch
plus the validator-first ordering and the UPSTREAM-exception path.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import requests
from _fixtures_loader import (
    finviz_empty_html,
    finviz_happy_html,
    finviz_malformed_row_html,
    finviz_no_table_html,
    finviz_one_page_html,
    finviz_redesign_html,
    finviz_ticker_mismatch_html,
    finviz_zero_redesign_html,
)
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Happy-path success — one row, no pagination markup.
# ---------------------------------------------------------------------------


def test_post_screens_happy_fixture_returns_one_stock(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_happy.html`` (1 row, no pagination) -> 200 with 1 stock.

    No row doubling here: the fixture has no ``screener-pages`` anchors so
    ``page_count == 0`` and ``fetch_urls(quarry, 0)`` issues exactly ONE
    fetch (see ``conftest.mock_fetch`` docstring for the doubling rule).
    Locks the full Stock shape so a future field rename / column-order
    change fails this regression.
    """
    mock_fetch.return_value = finviz_happy_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["schema_version"] == 1
    assert body["row_count"] == 1
    assert len(body["stocks"]) == 1

    stock = body["stocks"][0]
    # Verify the parsed shape end-to-end: ticker comes from the link text,
    # finviz_url is reconstructed by the adapter (spec §4.3 single-slash form).
    assert stock["ticker"] == "AAPL"
    assert stock["company"] == "Apple Inc."
    assert stock["sector"] == "Technology"
    assert stock["country"] == "USA"
    assert stock["rank"] == 1
    assert stock["finviz_url"] == "https://finviz.com/quote.ashx?t=AAPL"


# ---------------------------------------------------------------------------
# Single-page Finviz layout — the IndexError regression that started the
# whole umbrella spec. Asserts the pagination DOUBLING behavior end-to-end.
# ---------------------------------------------------------------------------


def test_post_screens_single_page_fixture_returns_six_rows(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_one_page.html`` (3 rows, 1 page marker) -> 200 with 6 stocks.

    Pagination doubling (T3 BACKEND surprise): the fixture's single
    ``<a class="screener-pages is-selected">1</a>`` element produces
    ``page_count == 1``, so ``fetch_urls`` issues ``range(1+1) == 2``
    fetches. Because ``mock_fetch`` returns the SAME fixture both times,
    the 3 rows are parsed twice -> 6. This is the test that would have
    caught the original ``content[-2]`` IndexError on the live single-page
    Finviz response shape.
    """
    mock_fetch.return_value = finviz_one_page_html()

    response = client.post(
        "/screens",
        json={"filters": {"fa_pe": "u5", "sec": "energy"}},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    # 3 rows in fixture × 2 fetches (pagination doubling) = 6.
    assert body["row_count"] == 6
    assert len(body["stocks"]) == 6
    # Tickers in order (AAPL/MSFT/XOM, repeated):
    tickers = [s["ticker"] for s in body["stocks"]]
    assert tickers == ["AAPL", "MSFT", "XOM", "AAPL", "MSFT", "XOM"]


# ---------------------------------------------------------------------------
# Zero-row success — empty <tbody>, valid HTML.
# ---------------------------------------------------------------------------


def test_post_screens_empty_fixture_returns_200_empty_stocks(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_empty.html`` (table present, empty tbody) -> 200 with []."""
    mock_fetch.return_value = finviz_empty_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_count"] == 0
    assert body["stocks"] == []


# ---------------------------------------------------------------------------
# Malformed row — parser AttributeError -> DATA classifier -> 502 parsing.
# ---------------------------------------------------------------------------


def test_post_screens_malformed_row_returns_502_parsing(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_malformed_row.html`` (no link anchor) -> 502 error_class=parsing.

    The row's second ``<td>`` has no ``<a>`` inside, so
    ``StockTableScreenerParser.ticker_link`` raises ``AttributeError`` when
    it calls ``cells[1].find('a').get('href')`` on ``None``.
    ``classify`` maps that to DATA (exit 4), and the exception handler
    maps DATA -> HTTP 502 with ``error_class="parsing"``. Empirically
    verified before this test was written.
    """
    mock_fetch.return_value = finviz_malformed_row_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 502
    body = response.json()
    assert body["schema_version"] == 1
    assert body["error_class"] == "parsing"
    # Every error envelope carries the correlation request_id for log correlation.
    assert body.get("request_id") is not None


# ---------------------------------------------------------------------------
# Missing table, no empty marker — MAJOR #4 closed. ``ScreenerLayoutError``
# now routes this through the DATA classifier -> 502 "parsing" instead of
# silently coercing to a 200 empty result.
# ---------------------------------------------------------------------------


def test_post_screens_no_table_returns_502_parsing(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_no_table.html`` (no table, no empty marker) -> 502 parsing.

    MAJOR #4 closed 2026-08-11: a missing screener table with no
    legitimate zero-result marker now raises ``ScreenerLayoutError`` in
    ``aggregate_rows``, classified DATA -> HTTP 502 ``error_class="parsing"``
    — no longer silently coerced to a 200 empty result.
    """
    mock_fetch.return_value = finviz_no_table_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 502
    body = response.json()
    assert body["error_class"] == "parsing"


# ---------------------------------------------------------------------------
# Legitimate zero-result page on the redesigned layout — no styled-table-new,
# but carries Finviz's js-screener-body-empty marker. Must stay 200/empty,
# NOT 502 parsing.
# ---------------------------------------------------------------------------


def test_post_screens_zero_redesign_returns_200_empty_stocks(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_zero_redesign.html`` (empty-result marker, no table) -> 200 []."""
    mock_fetch.return_value = finviz_zero_redesign_html()

    response = client.post("/screens", json={"filters": {"cap": "mega"}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_count"] == 0
    assert body["stocks"] == []


# ---------------------------------------------------------------------------
# Redesigned layout — issue #14 regression. Ticker cells must not duplicate
# their first letter.
# ---------------------------------------------------------------------------


def test_post_screens_redesign_fixture_returns_correct_tickers(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_redesign.html`` (2 rows, redesigned layout) -> tickers un-duplicated.

    Regression for GitHub issue #14: the old cell-wide ``get_text()``
    concatenated the logo-fallback anchor's single letter with the
    tab-link anchor's full ticker (e.g. "A" -> "AA", "AA" -> "AAA").
    """
    mock_fetch.return_value = finviz_redesign_html()

    response = client.post("/screens", json={"filters": {"cap": "midover"}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_count"] == 2
    tickers = [s["ticker"] for s in body["stocks"]]
    assert tickers == ["A", "AA"]


# ---------------------------------------------------------------------------
# Corrupted/drifted ticker cell — text disagrees with its href.
# ---------------------------------------------------------------------------


def test_post_screens_ticker_mismatch_returns_502_parsing(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_ticker_mismatch.html`` -> 502 error_class=parsing.

    The row's last anchor text ("KKTOS") disagrees with its href's ``t``
    query parameter ("KTOS"). ``ticker_symbol`` raises
    ``ScreenerLayoutError`` rather than returning the corrupted text;
    classified DATA -> HTTP 502 ``parsing``.
    """
    mock_fetch.return_value = finviz_ticker_mismatch_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 502
    body = response.json()
    assert body["error_class"] == "parsing"


# ---------------------------------------------------------------------------
# Validator-first gate — unknown filter key -> HTTP 422 (no fetch fires).
# ---------------------------------------------------------------------------


def test_post_screens_unknown_filter_key_returns_422(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """Unknown filter key -> 422 validation, NEVER reaches the fetch.

    Pins the spec §5 + T4b ordering invariant: ``validate_filter_pairs``
    runs BEFORE the adapter, so a typo like ``sec=enrgy`` produces a clean
    HTTP 422 instead of a deceptive 200/empty (the old silent-drop hazard).
    """
    response = client.post(
        "/screens",
        json={"filters": {"definitely_not_a_real_key": "u20"}},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_class"] == "validation"
    # Per the observability standard, every error envelope now carries the
    # correlation request_id (matching the echoed X-Request-ID), not just 5xx.
    assert isinstance(body.get("request_id"), str) and body["request_id"]
    # And critically — the mocked fetch was never invoked, proving the
    # validator gate fired before any pipeline work.
    mock_fetch.assert_not_called()


# ---------------------------------------------------------------------------
# UPSTREAM failure — fetch_page_sync raises a requests exception.
# ---------------------------------------------------------------------------


def test_post_screens_upstream_connection_error_returns_502_upstream(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``requests.ConnectionError`` from fetch -> 502 error_class=upstream.

    Pins the spec §5.1 UPSTREAM mapping end-to-end: the classifier maps
    ``requests.RequestException`` subclasses to UPSTREAM (exit 3), and the
    handler maps UPSTREAM -> HTTP 502 with ``error_class="upstream"``.
    """
    mock_fetch.side_effect = requests.exceptions.ConnectionError("connection refused")

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 502
    body = response.json()
    assert body["error_class"] == "upstream"
    assert body.get("request_id") is not None


# ---------------------------------------------------------------------------
# URL normalization regression — finviz_url uses single slash, not double.
# ---------------------------------------------------------------------------


def test_post_screens_finviz_url_uses_single_slash(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """All returned stocks have ``finviz_url`` with no ``//`` after host.

    The legacy CSV path emits ``https://finviz.com//quote.ashx?t=...``
    (BASE_URL ends with ``/``, href starts with ``/``). The adapter
    normalizes to the spec §4.3 single-slash form; this test pins that
    invariant against every row in a multi-stock response.
    """
    mock_fetch.return_value = finviz_one_page_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u5"}})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["row_count"] > 0
    for stock in body["stocks"]:
        url = stock["finviz_url"]
        assert url.startswith("https://finviz.com/quote.ashx?t="), url
        # Specifically reject the legacy double-slash form.
        assert "//quote" not in url, f"Double-slash regression in {url!r}"
