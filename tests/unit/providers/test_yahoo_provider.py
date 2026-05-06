from __future__ import annotations

import pandas as pd
import pytest

from finpack.providers.yfinance_provider import YFinanceProvider


class DummyTicker:
    def __init__(self, symbol: str, *, info: dict | None = None,
                 hist_df: pd.DataFrame | None = None,
                 balance_df: pd.DataFrame | None = None) -> None:
        self._symbol = symbol
        self.info = info or {"currentPrice": 123.45, "sharesOutstanding": 10}
        self._hist_df = hist_df if hist_df is not None else pd.DataFrame({"close": [1, 2, 3]})
        self._balance_df = balance_df if balance_df is not None else pd.DataFrame({
            "Total Assets": [300],
            "Current Assets": [100],
        }).T

    def history(self, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return self._hist_df

    @property
    def balance_sheet(self) -> pd.DataFrame:
        return self._balance_df


@pytest.fixture(autouse=True)
def patch_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    import finpack.providers.yfinance_provider as mod

    class FakeYF:
        def Ticker(self, symbol: str):  # type: ignore[override]
            return DummyTicker(symbol)

    monkeypatch.setattr(mod, "yf", FakeYF())


def test_get_info_returns_mapping():
    yp = YFinanceProvider()
    info = yp.get_info("AAPL")
    assert isinstance(info, dict)
    assert "currentPrice" in info


def test_get_history_returns_dataframe():
    yp = YFinanceProvider()
    df = yp.get_history("AAPL", period="1mo", interval="1d")
    assert isinstance(df, pd.DataFrame)
    assert "close" in df.columns or len(df) == 0


def test_get_balance_sheet_returns_dataframe():
    yp = YFinanceProvider()
    df = yp.get_balance_sheet("AAPL")
    assert isinstance(df, pd.DataFrame)


