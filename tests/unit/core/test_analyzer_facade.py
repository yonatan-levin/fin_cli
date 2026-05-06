from __future__ import annotations

import pandas as pd
import pytest

from finpack.core.analyzer import FundamentalAnalyzer


class DummyProvider:
    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame([
            {"TotalAssets": 300, "CurrentAssets": 100},
        ])

    def get_info(self, symbol: str):
        return {"regularMarketPrice": 150.0, "sharesOutstanding": 10.0}

    def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> pd.DataFrame:
        # Return history with median of 150 to match old test expectations
        return pd.DataFrame({"close": [140, 150, 160]})


def test_analyzer_ratios():
    """Test analyzer ratios using 30-day median price in ratios."""
    a = FundamentalAnalyzer(provider=DummyProvider())
    r = a.ratios("AAPL")
    
    # Per-share metrics (unchanged)
    assert r["price_by_assets"] == 30.0
    assert r["price_by_current_assets"] == 10.0
    
    # Ratios now use 30-day median price (150) instead of current price
    # ratio = 30day_median / price_by_assets = 150 / 30 = 5.0
    assert pytest.approx(r["price/price_to_assets_ratio"], 0.001) == 5.0
    # ratio = 30day_median / price_by_current_assets = 150 / 10 = 15.0
    assert pytest.approx(r["price/price_to_current_assets_ratio"], 0.001) == 15.0
