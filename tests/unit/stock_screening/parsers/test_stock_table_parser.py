from __future__ import annotations

from typing import cast

import pytest
from bs4 import BeautifulSoup, Tag

from fincli.resource.params.const import BASE_URL
from fincli.stock_screening.errors import ScreenerLayoutError
from fincli.stock_screening.parsers.stock_table import StockTableScreenerParser


def _table(html: str) -> Tag:
    return cast(Tag, BeautifulSoup(html, "html.parser").find("table"))


def _cells(row_html: str) -> list[Tag]:
    row = cast(Tag, BeautifulSoup(row_html, "html.parser").find("tr"))
    return row.find_all("td")


def test_parser_repr_identifies_underlying_content() -> None:
    table = _table("<table><tr></tr></table>")

    assert repr(StockTableScreenerParser(table)) == f"StockScreenerParser({table})"


def test_valid_row_returns_stripped_cells_and_absolute_ticker_link() -> None:
    parser = StockTableScreenerParser(
        _table(
            """
            <table>
              <tr valign="top">
                <td> 1 </td>
                <td><a href="/quote.ashx?t=AAPL"> AAPL </a></td>
              </tr>
            </table>
            """
        )
    )

    assert parser.table_data == [["1", "AAPL", f"{BASE_URL}/quote.ashx?t=AAPL"]]


def test_table_without_matching_rows_returns_empty_data() -> None:
    parser = StockTableScreenerParser(_table("<table><tr><td>ignored</td></tr></table>"))

    assert parser.table_rows == []
    assert parser.table_data == []


def test_missing_ticker_anchor_preserves_attribute_error_contract() -> None:
    parser = StockTableScreenerParser(
        _table(
            """
            <table>
              <tr valign="top"><td>1</td><td>AAPL</td></tr>
            </table>
            """
        )
    )

    with pytest.raises(AttributeError):
        _ = parser.table_data


# ---------------------------------------------------------------------------
# `ticker_symbol` — issue #14 regression (redesigned-layout dual-anchor cell)
# and the layout-drift guard (ScreenerLayoutError).
# ---------------------------------------------------------------------------


def test_ticker_symbol_legacy_single_anchor_cell_returns_text() -> None:
    """Old layout (single `<a>`): returns its text, matching href `t`."""
    cells = _cells('<tr><td>1</td><td><a href="/quote.ashx?t=AAPL">AAPL</a></td></tr>')

    assert StockTableScreenerParser.ticker_symbol(cells) == "AAPL"


def test_ticker_symbol_redesigned_dual_anchor_cell_reads_last_anchor_only() -> None:
    """New layout (logo-fallback anchor + tab-link anchor): no duplication.

    Regression for issue #14: `cell.get_text()` over the whole cell would
    concatenate the logo-fallback span's single letter with the tab-link's
    full ticker (e.g. "A" + "AA" -> "AAA"). `ticker_symbol` reads only the
    last anchor's text.
    """
    cells = _cells(
        '<tr><td>2</td><td><span class="flex items-center gap-1 pl-0.5">'
        '<a class="company-ticker" href="stock?t=AA&ty=c&p=d&b=1">'
        '<img src="logo.svg"><span>A</span></a>'
        '<a href="stock?t=AA&ty=c&p=d&b=1" class="tab-link">AA</a>'
        "</span></td></tr>"
    )

    assert StockTableScreenerParser.ticker_symbol(cells) == "AA"


def test_ticker_symbol_mismatched_text_and_href_raises_layout_error() -> None:
    """Last anchor's text disagrees with its href `t` param -> raise, don't return."""
    cells = _cells('<tr><td>1</td><td><a href="stock?t=KTOS&ty=c&p=d&b=1">KKTOS</a></td></tr>')

    with pytest.raises(ScreenerLayoutError, match="KKTOS"):
        StockTableScreenerParser.ticker_symbol(cells)


def test_ticker_symbol_missing_t_param_raises_layout_error() -> None:
    """Href with no `t` query parameter at all -> raise, never silently return."""
    cells = _cells('<tr><td>1</td><td><a href="stock?ty=c&p=d&b=1">AAPL</a></td></tr>')

    with pytest.raises(ScreenerLayoutError):
        StockTableScreenerParser.ticker_symbol(cells)


def test_ticker_symbol_no_anchor_falls_back_to_cell_text() -> None:
    """No `<a>` in the cell: return the plain text rather than raising here.

    `ticker_link`'s own `.find("a")` call is what raises `AttributeError`
    in this shape — `ticker_symbol` must not mask that existing contract.
    """
    cells = _cells("<tr><td>1</td><td>AAPL-no-anchor</td></tr>")

    assert StockTableScreenerParser.ticker_symbol(cells) == "AAPL-no-anchor"
