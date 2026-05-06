"""Edge case tests for finpack API to improve coverage.

Tests verify:
1. analyze() handles missing optional fields gracefully
2. enrich() handles edge cases (empty DataFrame, missing Symbol column)
3. Error handling for network/data issues
"""

from __future__ import annotations

import pandas as pd
import pytest

from finpack import api


class FakeAnalyzerEmpty:
    """Fake analyzer that returns empty results."""

    def ratios_batch(self, symbols):
        return pd.DataFrame()


class FakeAnalyzerPartial:
    """Fake analyzer with partial data (missing optional fields)."""

    def ratios_batch(self, symbols):
        # Return minimal data without optional fields
        return pd.DataFrame(
            [
                {
                    "Symbol": "TEST",
                    "sector": "Technology",
                    "industry": "Software",
                    "country": "USA",
                    "price_by_assets": 100.0,
                    "price_by_current_assets": 40.0,
                    "price/price_to_current_assets_ratio": 4.0,
                    "price/price_to_assets_ratio": 1.5,
                    # Missing: market_cap, average_price_30d
                }
            ]
        )


def test_analyze_with_empty_result(monkeypatch):
    """Verify analyze() handles empty analyzer results."""
    fake_analyzer = FakeAnalyzerEmpty()
    monkeypatch.setattr(api, "FundamentalAnalyzer", lambda: fake_analyzer)

    df = api.analyze(["INVALID"])
    assert df.empty


def test_analyze_with_missing_optional_fields(monkeypatch):
    """Verify analyze() handles missing optional fields (market_cap, average_price_30d)."""
    fake_analyzer = FakeAnalyzerPartial()
    monkeypatch.setattr(api, "FundamentalAnalyzer", lambda: fake_analyzer)

    df = api.analyze(["TEST"])
    
    assert len(df) == 1
    assert df.iloc[0]["Ticker"] == "TEST"
    # Optional fields should be None when missing
    assert df.iloc[0]["Market Cap"] is None
    assert df.iloc[0]["Average Price in Last 30 Days"] is None


def test_enrich_with_empty_screen_df():
    """Verify enrich() handles empty screen DataFrame."""
    empty_df = pd.DataFrame()
    result = api.enrich(empty_df)
    assert result.empty


def test_enrich_with_missing_symbol_column():
    """Verify enrich() handles screen DataFrame without Symbol column."""
    df_without_symbol = pd.DataFrame(
        {"Ticker": ["AAPL"], "Company": ["Apple Inc."]}
    )
    result = api.enrich(df_without_symbol)
    # Should return original DataFrame unchanged
    assert "Ticker" in result.columns
    assert "Company" in result.columns


def test_enrich_with_empty_analysis_result(monkeypatch):
    """Verify enrich() handles case where analyze returns empty."""
    fake_analyzer = FakeAnalyzerEmpty()
    monkeypatch.setattr(api, "FundamentalAnalyzer", lambda: fake_analyzer)

    screen_df = pd.DataFrame(
        {
            "Symbol": ["AAPL"],
            "Ticker": ["AAPL"],
            "Company": ["Apple Inc."],
        }
    )
    
    result = api.enrich(screen_df)
    
    # Should return original screen_df when analysis is empty
    assert len(result) == 1
    assert "Company" in result.columns


def test_analyze_preserves_column_order_with_partial_data(monkeypatch):
    """Verify analyze() enforces column order even with missing fields."""
    fake_analyzer = FakeAnalyzerPartial()
    monkeypatch.setattr(api, "FundamentalAnalyzer", lambda: fake_analyzer)

    df = api.analyze(["TEST"])
    
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

