"""Unit tests for ``fincli.app.main.scrape_link_to_dataframe``.

Mirrors the mock-target rule used across the suite: patch
``fincli.app.main.fetch_page_sync`` (the local binding resolved inside
``main`` at import time), never ``fincli.utils.web_scraper.fetch_page_sync``
directly. Scope is narrow — pin that ``scrape_link_to_dataframe`` delegates
to the same shared ``_screen_from_query`` core as ``screen_to_dataframe``
(fetches the URL verbatim, no query-building, no filter validation) so the
two entry points cannot drift on the parser/coercion contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest

from fincli.app.main import scrape_link_to_dataframe

# Mirrors `tests/integration/fixtures/finviz_happy.html` exactly (one row,
# no pagination markup) so the parser's expected table shape matches.
_HAPPY_ROW_HTML = b"""<html><body>
<table class="styled-table-new"><tbody>
<tr valign="top">
  <td>1</td>
  <td><a href="/quote.ashx?t=AAPL">AAPL</a></td>
  <td>Apple Inc.</td>
  <td>Technology</td>
  <td>Consumer Electronics</td>
  <td>USA</td>
  <td>2.89T</td>
  <td>28.52</td>
  <td>182.63</td>
  <td>-1.23%</td>
  <td>52,436,789</td>
</tr>
</tbody></table>
</body></html>
"""


@pytest.fixture
def mock_fetch() -> Iterator[MagicMock]:
    """Patch the module-local ``fetch_page_sync`` binding inside ``fincli.app.main``."""
    with patch("fincli.app.main.fetch_page_sync") as m:
        m.return_value = _HAPPY_ROW_HTML
        yield m


def test_scrape_link_to_dataframe_fetches_url_verbatim(mock_fetch: MagicMock) -> None:
    """The supplied URL is used verbatim as the fetch target — no query building."""
    url = "https://finviz.com/screener.ashx?v=111&f=fa_sales3years_pos,ta_perf2_3yup&ft=2"

    scrape_link_to_dataframe(url)

    # First call is the page-count discovery fetch; it must be the verbatim URL,
    # confirming no `build_stock_screener_query` transformation happened.
    first_call_url = mock_fetch.call_args_list[0].args[0]
    assert first_call_url == url


def test_scrape_link_to_dataframe_returns_parsed_frame(mock_fetch: MagicMock) -> None:
    """Delegates to the shared ``_screen_from_query`` core — same parser/coercion
    contract as ``screen_to_dataframe`` (CONTRACTS §3.1 columns)."""
    df = scrape_link_to_dataframe("https://finviz.com/screener.ashx?v=111&f=fa_pe_u20")

    assert len(df) == 1
    assert df.iloc[0]["Symbol"] == "AAPL"
    assert df.iloc[0]["Ticker"] == "AAPL"  # hyperlink_wrap defaults to False


def test_scrape_link_to_dataframe_hyperlink_wrap_true_wraps_ticker(mock_fetch: MagicMock) -> None:
    """``hyperlink_wrap=True`` reproduces the CLI file-destination Excel formula."""
    df = scrape_link_to_dataframe(
        "https://finviz.com/screener.ashx?v=111&f=fa_pe_u20", hyperlink_wrap=True
    )

    assert df.iloc[0]["Ticker"].startswith('=HYPERLINK("')
