from __future__ import annotations

from typing import cast

import pytest
from bs4 import BeautifulSoup, Tag

from fincli.resource.params.const import BASE_URL
from fincli.stock_screening.parsers.stock_table import StockTableScreenerParser


def _table(html: str) -> Tag:
    return cast(Tag, BeautifulSoup(html, "html.parser").find("table"))


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
