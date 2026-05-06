"""Unit tests for finpack public API facade.

Tests verify:
1. screen() delegates to StockScreener and returns DataFrame
2. analyze() delegates to FundamentalAnalyzer and returns structured DataFrame
3. enrich() merges screen and analyze results on Symbol/Ticker
"""

from __future__ import annotations

import pandas as pd
import pytest

from finpack import api


class FakeScreener:
    """Fake screener for testing."""

    def __init__(self, screen_result: pd.DataFrame | None = None) -> None:
        self._result = (
            screen_result
            if screen_result is not None
            else pd.DataFrame(
                {
                    "No.": [1, 2],
                    "Ticker": ["AAPL", "MSFT"],
                    "Symbol": ["AAPL", "MSFT"],
                    "Company": ["Apple Inc.", "Microsoft Corp."],
                    "Sector": ["Technology", "Technology"],
                    "Industry": ["Consumer Electronics", "Software"],
                    "Country": ["USA", "USA"],
                    "Market Cap": [3000000000000, 2500000000000],
                    "P/E": [30.5, 35.2],
                    "Price": [180.0, 350.0],
                    "Change": [1.5, -0.5],
                    "Volume": [50000000, 30000000],
                }
            )
        )

    def screen(self, filters=None, scrape_link=None):
        return self._result


class FakeAnalyzer:
    """Fake analyzer for testing."""

    def __init__(self, ratios_result: pd.DataFrame | None = None) -> None:
        self._result = (
            ratios_result
            if ratios_result is not None
            else pd.DataFrame(
                [
                    {
                        "Symbol": "AAPL",
                        "sector": "Technology",
                        "industry": "Consumer Electronics",
                        "country": "USA",
                        "market_cap": 3000000000000.0,
                        "average_price_30d": 175.0,
                        "price_by_assets": 100.0,
                        "price_by_current_assets": 40.0,
                        "price/price_to_current_assets_ratio": 4.375,
                        "price/price_to_assets_ratio": 1.75,
                    },
                    {
                        "Symbol": "MSFT",
                        "sector": "Technology",
                        "industry": "Software—Infrastructure",
                        "country": "USA",
                        "market_cap": 2500000000000.0,
                        "average_price_30d": 345.0,
                        "price_by_assets": 120.0,
                        "price_by_current_assets": 50.0,
                        "price/price_to_current_assets_ratio": 6.9,
                        "price/price_to_assets_ratio": 2.875,
                    },
                ]
            )
        )

    def ratios_batch(self, symbols):
        # Filter to requested symbols
        return self._result[self._result["Symbol"].isin(symbols)].copy()


def test_screen_delegates_to_screener(monkeypatch):
    """Verify screen() delegates to StockScreener.screen()."""
    fake_screener = FakeScreener()
    monkeypatch.setattr(api, "StockScreener", lambda: fake_screener)

    df = api.screen(filters=[("cap", "midover")])

    assert len(df) == 2
    assert list(df["Symbol"]) == ["AAPL", "MSFT"]
    assert "Ticker" in df.columns
    assert "Company" in df.columns


def test_screen_with_scrape_link(monkeypatch):
    """Verify screen() accepts scrape_link argument."""
    fake_screener = FakeScreener()
    monkeypatch.setattr(api, "StockScreener", lambda: fake_screener)

    df = api.screen(scrape_link="https://finviz.com/screener.ashx?v=111&f=cap_midover")

    assert len(df) == 2


def test_analyze_delegates_to_analyzer(monkeypatch):
    """Verify analyze() delegates to FundamentalAnalyzer.ratios_batch()."""
    fake_analyzer = FakeAnalyzer()
    monkeypatch.setattr(api, "FundamentalAnalyzer", lambda: fake_analyzer)

    symbols = ["AAPL", "MSFT"]
    df = api.analyze(symbols)

    assert len(df) == 2
    # Verify expected columns with proper names
    assert "Ticker" in df.columns  # Renamed from Symbol
    assert "Sector" in df.columns  # Capitalized
    assert "Industry" in df.columns
    assert "Country" in df.columns
    assert "Market Cap" in df.columns
    assert "Average Price in Last 30 Days" in df.columns
    assert "price_by_assets" in df.columns
    assert "price_by_current_assets" in df.columns
    assert "price/price_to_current_assets_ratio" in df.columns
    assert "price/price_to_assets_ratio" in df.columns


def test_analyze_returns_canonical_column_order():
    """Verify analyze() enforces canonical column order."""
    fake_analyzer = FakeAnalyzer()

    # Monkeypatch inside test
    import finpack.api as api_module

    original_analyzer = api_module.FundamentalAnalyzer
    api_module.FundamentalAnalyzer = lambda: fake_analyzer

    try:
        df = api.analyze(["AAPL"])
        # Check exact column order
        expected_cols = [
            "Ticker",
            "Sector",
            "Industry",
            "Country",
            "Market Cap",
            "Average Price in Last 30 Days",
            "price_by_assets",
            "price_by_current_assets",
            "price/price_to_current_assets_ratio",
            "price/price_to_assets_ratio",
        ]
        assert list(df.columns) == expected_cols
    finally:
        api_module.FundamentalAnalyzer = original_analyzer


def test_enrich_merges_screen_and_analyze_results(monkeypatch):
    """Verify enrich() merges screening and analysis DataFrames."""
    fake_screener = FakeScreener()
    fake_analyzer = FakeAnalyzer()

    monkeypatch.setattr(api, "StockScreener", lambda: fake_screener)
    monkeypatch.setattr(api, "FundamentalAnalyzer", lambda: fake_analyzer)

    screen_df = api.screen(filters=[("cap", "midover")])
    enriched = api.enrich(screen_df)

    assert len(enriched) == 2
    # Verify columns from both screen and analyze
    assert "Company" in enriched.columns  # From screen
    assert "price_by_assets" in enriched.columns  # From analyze
    assert "Sector" in enriched.columns  # From analyze (overwrites screen)


def test_analyze_handles_empty_symbol_list():
    """Verify analyze() returns empty DataFrame for empty symbol list."""
    df = api.analyze([])
    assert df.empty


def test_analyze_handles_single_symbol():
    """Verify analyze() works with a single symbol."""
    fake_analyzer = FakeAnalyzer(
        ratios_result=pd.DataFrame(
            [
                {
                    "Symbol": "AAPL",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "country": "USA",
                    "market_cap": 3000000000000.0,
                    "average_price_30d": 175.0,
                    "price_by_assets": 100.0,
                    "price_by_current_assets": 40.0,
                    "price/price_to_current_assets_ratio": 4.375,
                    "price/price_to_assets_ratio": 1.75,
                }
            ]
        )
    )

    import finpack.api as api_module

    original = api_module.FundamentalAnalyzer
    api_module.FundamentalAnalyzer = lambda: fake_analyzer

    try:
        df = api.analyze(["AAPL"])
        assert len(df) == 1
        assert df.iloc[0]["Ticker"] == "AAPL"
    finally:
        api_module.FundamentalAnalyzer = original

