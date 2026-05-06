"""E2E tests for the new two-step API.

These tests replace the old pipeline tests and verify:
1. finpack.analyze() produces expected DataFrame structure
2. finpack.screen() + finpack.analyze() workflow
3. finpack.enrich() merges results correctly
"""

from __future__ import annotations

import pandas as pd
import pytest

import finpack


class DummyAnalyzer:
    """Fake analyzer with predefined ratios for testing."""

    def __init__(self, ratios_map: dict) -> None:
        self._map = ratios_map

    def ratios_batch(self, symbols):
        rows = []
        for sym in symbols:
            if sym in self._map:
                row = {"Symbol": sym, **self._map[sym]}
                rows.append(row)
        return pd.DataFrame(rows)


def test_analyze_returns_expected_structure():
    """Verify analyze() returns DataFrame with canonical columns."""
    # Use a fake analyzer for deterministic results
    ratios_map = {
        "AAPL": {
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "USA",
            "market_cap": 3.557e12,
            "average_price_30d": 230.10,
            "price_by_assets": 16.75,
            "price_by_current_assets": 7.40,
            "price/price_to_current_assets_ratio": 31.06,
            "price/price_to_assets_ratio": 13.73,
        }
    }

    fake_analyzer = DummyAnalyzer(ratios_map)

    # Monkeypatch to use fake analyzer
    import finpack.api as api_module

    original_analyzer = api_module.FundamentalAnalyzer
    api_module.FundamentalAnalyzer = lambda: fake_analyzer

    try:
        df = finpack.analyze(["AAPL"])

        # Verify structure
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
        assert df.iloc[0]["Ticker"] == "AAPL"
        assert df.iloc[0]["Sector"] == "Technology"
        assert round(df.iloc[0]["price_by_assets"], 2) == 16.75
        assert round(df.iloc[0]["Market Cap"], 2) == 3.557e12

    finally:
        api_module.FundamentalAnalyzer = original_analyzer


def test_analyze_multiple_symbols():
    """Verify analyze() handles multiple symbols correctly."""
    ratios_map = {
        "AAPL": {
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "USA",
            "market_cap": 3.557e12,
            "average_price_30d": 230.10,
            "price_by_assets": 16.75,
            "price_by_current_assets": 7.40,
            "price/price_to_current_assets_ratio": 31.06,
            "price/price_to_assets_ratio": 13.73,
        },
        "MSFT": {
            "sector": "Technology",
            "industry": "Software—Infrastructure",
            "country": "USA",
            "market_cap": 2.5e12,
            "average_price_30d": 350.00,
            "price_by_assets": 63.09,
            "price_by_current_assets": 35.16,
            "price/price_to_current_assets_ratio": 6.66,
            "price/price_to_assets_ratio": 11.96,
        },
    }

    fake_analyzer = DummyAnalyzer(ratios_map)

    import finpack.api as api_module

    original_analyzer = api_module.FundamentalAnalyzer
    api_module.FundamentalAnalyzer = lambda: fake_analyzer

    try:
        df = finpack.analyze(["AAPL", "MSFT"])

        assert len(df) == 2
        assert df.iloc[0]["Ticker"] == "AAPL"
        assert df.iloc[1]["Ticker"] == "MSFT"
        assert round(df.iloc[1]["price_by_assets"], 2) == 63.09

    finally:
        api_module.FundamentalAnalyzer = original_analyzer


def test_two_step_workflow():
    """Test the complete two-step workflow: screen → analyze."""
    # This would normally hit the network, so we use a minimal mock

    class FakeScreener:
        def screen(self, filters=None, scrape_link=None):
            return pd.DataFrame(
                {
                    "Symbol": ["AAPL", "MSFT"],
                    "Ticker": ["AAPL", "MSFT"],
                    "Company": ["Apple Inc.", "Microsoft"],
                    "Sector": ["Technology", "Technology"],
                    "Market Cap": [3e12, 2.5e12],
                }
            )

    ratios_map = {
        "AAPL": {
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "USA",
            "market_cap": 3e12,
            "average_price_30d": 230.0,
            "price_by_assets": 16.75,
            "price_by_current_assets": 7.40,
            "price/price_to_current_assets_ratio": 31.06,
            "price/price_to_assets_ratio": 13.73,
        },
        "MSFT": {
            "sector": "Technology",
            "industry": "Software",
            "country": "USA",
            "market_cap": 2.5e12,
            "average_price_30d": 350.0,
            "price_by_assets": 63.09,
            "price_by_current_assets": 35.16,
            "price/price_to_current_assets_ratio": 6.66,
            "price/price_to_assets_ratio": 11.96,
        },
    }

    fake_analyzer = DummyAnalyzer(ratios_map)

    import finpack.api as api_module

    original_screener = api_module.StockScreener
    original_analyzer = api_module.FundamentalAnalyzer

    api_module.StockScreener = FakeScreener
    api_module.FundamentalAnalyzer = lambda: fake_analyzer

    try:
        # Step 1: Screen
        screen_df = finpack.screen(filters=[("cap", "midover")])
        assert len(screen_df) == 2

        # Step 2: Analyze
        symbols = screen_df["Symbol"].tolist()
        analysis_df = finpack.analyze(symbols)
        assert len(analysis_df) == 2
        assert "price_by_assets" in analysis_df.columns

        # Step 3: Enrich
        enriched = finpack.enrich(screen_df)
        assert len(enriched) == 2
        assert "Company" in enriched.columns  # From screen
        assert "price_by_assets" in enriched.columns  # From analyze

    finally:
        api_module.StockScreener = original_screener
        api_module.FundamentalAnalyzer = original_analyzer

