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

import pytest
import requests
from _fixtures_loader import (
    finviz_empty_html,
    finviz_happy_html,
    finviz_malformed_row_html,
    finviz_no_table_html,
    finviz_one_page_html,
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
    # 5xx envelopes carry a request_id for log correlation; 4xx do not.
    assert body.get("request_id") is not None


# ---------------------------------------------------------------------------
# Missing table — MAJOR #4 deferred limitation. Currently coerced to a 200
# empty result instead of 502 "parsing". Documented as ``xfail`` so when
# the limitation is closed the test starts passing and the marker can drop.
# ---------------------------------------------------------------------------


@pytest.mark.xfail(
    reason=(
        "MAJOR #4 deferred (see exception_handlers.py module docstring): "
        "malformed HTML with no styled-table-new element currently routes "
        "through the zero-row success branch (200, empty stocks) instead "
        "of the 502 parsing envelope spec §5.1 implies. Closing requires "
        "parser-level changes in fincli/stock_screening/ — out of T5 scope."
    ),
    strict=True,
)
def test_post_screens_no_table_returns_502_parsing(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """``finviz_no_table.html`` (no table element) -> 502 error_class=parsing.

    Spec §5.1 implies "malformed Finviz response" should classify as
    parsing (502), but the current ``page_count == 0`` + empty
    ``all_table_content`` branch silently routes to 200/empty. Marked
    ``xfail(strict=True)`` so closing MAJOR #4 will trip the marker and
    force a docs update.

    PAIRED WITH ``test_post_screens_no_table_current_behavior_returns_200_empty``
    below — both tests must be flipped/deleted in the same commit when
    MAJOR #4 closes (strict=True ensures the pair stays mechanically coupled).
    """
    mock_fetch.return_value = finviz_no_table_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 502
    body = response.json()
    assert body["error_class"] == "parsing"


def test_post_screens_no_table_current_behavior_returns_200_empty(
    client: TestClient, mock_fetch: MagicMock
) -> None:
    """Document the ACTUAL current behavior of the no-table fixture.

    Pinned alongside the ``xfail`` above so the current MAJOR #4 limitation
    is testable and visible. When the limitation is closed, this test must
    be flipped (delete or invert) at the same time as the xfail marker is
    removed.

    PAIRED WITH ``test_post_screens_no_table_returns_502_parsing`` above —
    closing MAJOR #4 flips strict=True xfail to "unexpected pass" AND
    breaks this current-behavior assertion. The pair must be edited
    together in a single commit.
    """
    mock_fetch.return_value = finviz_no_table_html()

    response = client.post("/screens", json={"filters": {"fa_pe": "u20"}})

    assert response.status_code == 200
    body = response.json()
    assert body["row_count"] == 0
    assert body["stocks"] == []


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
    # 4xx envelopes deliberately omit request_id (caller's fault).
    assert body.get("request_id") is None
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
