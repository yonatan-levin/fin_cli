from __future__ import annotations

import types

import pandas as pd
import pytest

from finpack.core.screener import StockScreener


HTML_PAGE = b"""
<html>
  <table class="styled-table-new"></table>
  <div class="screener-pages"><a>1</a><a>2</a><a>3</a></div>
</html>
"""


class DummyContent:
    def __init__(self):
        pass


@pytest.fixture(autouse=True)
def patch_scraper_and_parser(monkeypatch: pytest.MonkeyPatch):
    import finpack.core.screener as mod
    import finpack.models.stock_screening.content.stock_table as content_mod

    def fake_fetch(url: str) -> bytes:
        return HTML_PAGE

    class DummyParser:
        def __init__(self, e):
            pass

        @property
        def table_data(self):
            return [["1", "AAPL", "Apple", "Tech", "HW", "USA", "2.5T", "30", "150", "+1%", "1000", "http://example"]]

    class DummyScreenContent:
        def __init__(self, html):
            pass

        @property
        def all_table_content(self):
            return [DummyParser(None)]

        @property
        def page_count(self):
            return 0

    monkeypatch.setattr(mod, "fetch_page_sync", fake_fetch)
    monkeypatch.setattr(content_mod, "StockTableScreeningContent", DummyScreenContent)


def test_screener_builds_dataframe():
    s = StockScreener()
    df = s.screen(scrape_link="https://finviz.com/screener.ashx?v=111&f=cap_large")
    assert isinstance(df, pd.DataFrame)
    assert "Symbol" in df.columns
    assert df.iloc[0]["Symbol"] == "AAPL"
