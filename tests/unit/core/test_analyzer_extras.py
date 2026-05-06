from __future__ import annotations

import pandas as pd

from finpack.core.analyzer import FundamentalAnalyzer


class DummyProvider:
    def __init__(self) -> None:
        self._hist = pd.DataFrame({"close": [100, 200, 300]})
        self._balance = pd.DataFrame({"TotalAssets": [300], "CurrentAssets": [100]})
        self._info = {"currentPrice": 150.0, "sharesOutstanding": 10.0, "marketCap": 3.557e12}

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        return self._balance

    def get_info(self, symbol: str):
        return self._info

    def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        return self._hist


def test_analyzer_includes_average_price_and_market_cap():
    analyzer = FundamentalAnalyzer(provider=DummyProvider())
    r = analyzer.ratios("AAPL")
    assert r["market_cap"] == 3.557e12
    # median of [100,200,300] is 200
    assert r["average_price_30d"] == 200
