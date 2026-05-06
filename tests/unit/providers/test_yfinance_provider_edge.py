from __future__ import annotations

import pandas as pd
import pytest

from finpack.providers.yfinance_provider import YFinanceProvider


class EmptyTicker:
    info = {}

    def history(self, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return pd.DataFrame()

    @property
    def balance_sheet(self) -> pd.DataFrame:
        return pd.DataFrame()


@pytest.fixture(autouse=True)
def patch_yf_empty(monkeypatch: pytest.MonkeyPatch):
    import finpack.providers.yfinance_provider as mod

    class FakeYF:
        def Ticker(self, symbol: str):  # type: ignore[override]
            return EmptyTicker()

    monkeypatch.setattr(mod, "yf", FakeYF())
    yield


def test_get_info_empty_mapping():
    yp = YFinanceProvider()
    assert yp.get_info("XXXX") == {}


def test_get_history_empty_dataframe():
    yp = YFinanceProvider()
    df = yp.get_history("XXXX")
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_get_balance_sheet_empty_dataframe():
    yp = YFinanceProvider()
    df = yp.get_balance_sheet("XXXX")
    assert isinstance(df, pd.DataFrame)
    assert df.empty
