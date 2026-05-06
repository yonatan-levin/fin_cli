"""Unit tests for FundamentalAnalyzer with sector/industry/country descriptors.

Tests verify that:
1. Ratios use 30-day median price as numerator (not current price)
2. Sector, Industry, Country are extracted from info when present
3. Edge cases (missing fields, zero shares, empty history) are handled gracefully
"""

from __future__ import annotations

import pandas as pd
import pytest

from finpack.core.analyzer import FundamentalAnalyzer


class FakeProvider:
    """Deterministic fake provider for testing analyzer logic."""

    def __init__(
        self,
        balance_sheet: pd.DataFrame | None = None,
        info: dict | None = None,
        history: pd.DataFrame | None = None,
    ) -> None:
        self._balance = balance_sheet if balance_sheet is not None else pd.DataFrame()
        self._info = info if info is not None else {}
        self._history = history if history is not None else pd.DataFrame()

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        return self._balance

    def get_info(self, symbol: str) -> dict:
        return self._info

    def get_history(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> pd.DataFrame:
        return self._history


def test_analyzer_ratios_use_30day_median_price():
    """Verify ratios use 30-day median price as numerator, not current price."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame(
            [{"TotalAssets": 1000, "CurrentAssets": 400}]
        ),
        info={
            "currentPrice": 50.0,  # Current price (should NOT be used in ratios)
            "sharesOutstanding": 10.0,
            "marketCap": 500.0,
        },
        history=pd.DataFrame({"close": [10, 20, 30, 40, 50]}),  # median = 30
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    result = analyzer.ratios("TEST")

    # price_by_assets = TotalAssets / shares = 1000 / 10 = 100
    assert result["price_by_assets"] == 100.0

    # price_by_current_assets = CurrentAssets / shares = 400 / 10 = 40
    assert result["price_by_current_assets"] == 40.0

    # ratio = 30day_median / price_by_current_assets = 30 / 40 = 0.75
    assert pytest.approx(result["price/price_to_current_assets_ratio"], 0.001) == 0.75

    # ratio = 30day_median / price_by_assets = 30 / 100 = 0.3
    assert pytest.approx(result["price/price_to_assets_ratio"], 0.001) == 0.3

    # Verify 30-day median is included
    assert result["average_price_30d"] == 30.0


def test_analyzer_includes_sector_industry_country():
    """Verify sector, industry, country are extracted from info."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame([{"TotalAssets": 1000, "CurrentAssets": 400}]),
        info={
            "currentPrice": 100.0,
            "sharesOutstanding": 10.0,
            "marketCap": 1000.0,
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "country": "United States",
        },
        history=pd.DataFrame({"close": [100]}),
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    result = analyzer.ratios("MSFT")

    assert result["sector"] == "Technology"
    assert result["industry"] == "Software—Infrastructure"
    assert result["country"] == "United States"


def test_analyzer_handles_missing_descriptors():
    """Verify graceful handling when sector/industry/country are missing."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame([{"TotalAssets": 500, "CurrentAssets": 200}]),
        info={"currentPrice": 50.0, "sharesOutstanding": 10.0, "marketCap": 500.0},
        history=pd.DataFrame({"close": [50]}),
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    result = analyzer.ratios("UNKNOWN")

    # Should default to empty string
    assert result.get("sector", "") == ""
    assert result.get("industry", "") == ""
    assert result.get("country", "") == ""


def test_analyzer_handles_empty_history():
    """Verify ratios default to zero when history is empty."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame([{"TotalAssets": 1000, "CurrentAssets": 400}]),
        info={"currentPrice": 100.0, "sharesOutstanding": 10.0, "marketCap": 1000.0},
        history=pd.DataFrame(),  # Empty history
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    result = analyzer.ratios("TEST")

    # price_by_assets/current_assets should still compute
    assert result["price_by_assets"] == 100.0
    assert result["price_by_current_assets"] == 40.0

    # Ratios should be zero when no 30-day price available
    assert result["price/price_to_current_assets_ratio"] == 0.0
    assert result["price/price_to_assets_ratio"] == 0.0

    # average_price_30d should be None
    assert result.get("average_price_30d") is None


def test_analyzer_handles_zero_shares():
    """Verify zero shares results in zero per-share metrics."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame([{"TotalAssets": 1000, "CurrentAssets": 400}]),
        info={"currentPrice": 100.0, "sharesOutstanding": 0.0, "marketCap": 0.0},
        history=pd.DataFrame({"close": [100]}),
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    result = analyzer.ratios("TEST")

    assert result["price_by_assets"] == 0.0
    assert result["price_by_current_assets"] == 0.0
    assert result["price/price_to_current_assets_ratio"] == 0.0
    assert result["price/price_to_assets_ratio"] == 0.0


def test_analyzer_handles_empty_balance_sheet():
    """Verify empty balance sheet returns empty dict."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame(),  # Empty
        info={"currentPrice": 100.0, "sharesOutstanding": 10.0},
        history=pd.DataFrame({"close": [100]}),
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    result = analyzer.ratios("TEST")

    assert result == {}


def test_analyzer_ratios_batch():
    """Verify batch processing returns DataFrame with all symbols."""
    provider = FakeProvider(
        balance_sheet=pd.DataFrame([{"TotalAssets": 1000, "CurrentAssets": 400}]),
        info={
            "currentPrice": 50.0,
            "sharesOutstanding": 10.0,
            "marketCap": 500.0,
            "sector": "Technology",
            "industry": "Software",
            "country": "USA",
        },
        history=pd.DataFrame({"close": [10, 20, 30]}),
    )

    analyzer = FundamentalAnalyzer(provider=provider)
    df = analyzer.ratios_batch(["AAPL", "MSFT"])

    assert len(df) == 2
    assert list(df["Symbol"]) == ["AAPL", "MSFT"]
    # Verify key columns exist
    assert "price_by_assets" in df.columns
    assert "sector" in df.columns
    assert "average_price_30d" in df.columns

