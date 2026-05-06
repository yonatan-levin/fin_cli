from __future__ import annotations

import pandas as pd
import pytest

from finpack.core.screener import StockScreener


@pytest.fixture(autouse=True)
def patch_empty_pages(monkeypatch: pytest.MonkeyPatch):
    import finpack.core.screener as mod
    import finpack.models.stock_screening.content.stock_table as content_mod

    def fake_fetch(url: str) -> bytes:
        return b"<html><div class='screener-pages'></div></html>"

    class DummyParser:
        @property
        def table_data(self):
            return []

    class DummyScreenContent:
        def __init__(self, html):
            pass

        @property
        def all_table_content(self):
            return []

        @property
        def page_count(self):
            return 0

    monkeypatch.setattr(mod, "fetch_page_sync", fake_fetch)
    monkeypatch.setattr(content_mod, "StockTableScreeningContent", DummyScreenContent)
    yield


def test_screener_empty_result_returns_empty_dataframe():
    s = StockScreener()
    df = s.screen(scrape_link="https://finviz.com/screener.ashx?v=111&f=cap_large")
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_screener_filters_input_builds_url(monkeypatch: pytest.MonkeyPatch):
    # Verify filters flow path without asserting URL (covered by query builder test)
    s = StockScreener()
    df = s.screen(filters=[("fa_pe", "u15")])
    assert isinstance(df, pd.DataFrame)
