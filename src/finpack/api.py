"""Public API facade for finpack library.

This module exposes simple, two-step functions for stock screening and fundamental analysis:
- screen(): Filter stocks using Finviz screener
- analyze(): Compute fundamental ratios for a list of symbols
- enrich(): Merge screening and analysis results

No CLI, no pipelines - just straightforward function calls.
"""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import pandas as pd

from .core.screener import StockScreener
from .core.analyzer import FundamentalAnalyzer


def screen(
    filters: Iterable[Tuple[str, str]] | None = None, scrape_link: str | None = None
) -> pd.DataFrame:
    """Screen stocks using Finviz screener.

    Args:
        filters: Iterable of (filter_key, value_key) tuples for building Finviz query.
                 Example: [("cap", "midover"), ("fa_pe", "u40")]
        scrape_link: Direct Finviz screener URL (bypasses filters argument).

    Returns:
        DataFrame with columns: No., Ticker, Symbol, Company, Sector, Industry,
        Country, Market Cap, P/E, Price, Change, Volume.

    Examples:
        >>> import finpack
        >>> # Screen for mid-cap+ stocks with P/E under 40
        >>> df = finpack.screen(filters=[("cap", "midover"), ("fa_pe", "u40")])
        >>> print(df.head())

        >>> # Use a direct Finviz link
        >>> df = finpack.screen(scrape_link="https://finviz.com/screener.ashx?v=111&f=cap_midover")
    """
    screener = StockScreener()
    return screener.screen(filters=filters, scrape_link=scrape_link)


def analyze(symbols: Sequence[str]) -> pd.DataFrame:
    """Compute fundamental ratios and descriptors for a list of symbols.

    Args:
        symbols: List of stock symbols (e.g., ["AAPL", "MSFT", "GOOGL"])

    Returns:
        DataFrame with columns (in canonical order):
        - Ticker: Stock symbol
        - Sector: Company sector
        - Industry: Company industry
        - Country: Company country
        - Market Cap: Market capitalization
        - Average Price in Last 30 Days: 30-day median close price
        - price_by_assets: Total assets per share
        - price_by_current_assets: Current assets per share
        - price/price_to_current_assets_ratio: 30-day price / price_by_current_assets
        - price/price_to_assets_ratio: 30-day price / price_by_assets

    Examples:
        >>> import finpack
        >>> symbols = ["AAPL", "MSFT", "GOOGL"]
        >>> df = finpack.analyze(symbols)
        >>> print(df[["Ticker", "Sector", "Average Price in Last 30 Days"]])
    """
    if not symbols:
        return pd.DataFrame()

    analyzer = FundamentalAnalyzer()
    df = analyzer.ratios_batch(list(symbols))

    if df.empty:
        return df

    # Rename columns to match historical fundainsight output
    rename_map = {
        "Symbol": "Ticker",
        "sector": "Sector",
        "industry": "Industry",
        "country": "Country",
        "market_cap": "Market Cap",
        "average_price_30d": "Average Price in Last 30 Days",
    }
    df = df.rename(columns=rename_map)

    # Enforce canonical column order
    canonical_cols = [
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

    # Ensure all canonical columns exist (add missing with None)
    for col in canonical_cols:
        if col not in df.columns:
            df[col] = None

    return df[canonical_cols]


def enrich(screen_df: pd.DataFrame) -> pd.DataFrame:
    """Enrich screening results with fundamental analysis.

    Takes a DataFrame from screen() and adds fundamental ratios for each symbol.

    Args:
        screen_df: DataFrame returned from screen() with Symbol column

    Returns:
        DataFrame with columns from both screen() and analyze(), merged on Symbol.
        Analysis columns (Sector, Industry, Country) override screening columns.

    Examples:
        >>> import finpack
        >>> screen_df = finpack.screen(filters=[("cap", "midover")])
        >>> enriched = finpack.enrich(screen_df)
        >>> print(enriched[["Ticker", "Company", "price_by_assets", "Sector"]])
    """
    if screen_df.empty or "Symbol" not in screen_df.columns:
        return screen_df

    symbols = screen_df["Symbol"].unique().tolist()
    analysis_df = analyze(symbols)

    if analysis_df.empty:
        return screen_df

    # Rename Ticker back to Symbol for merge
    analysis_df = analysis_df.rename(columns={"Ticker": "Symbol"})

    # Merge: analysis columns override screen columns (e.g., Sector, Industry, Country)
    merged = screen_df.merge(
        analysis_df,
        on="Symbol",
        how="left",
        suffixes=("_screen", "_analysis"),
    )

    # Prefer analysis columns over screen columns for duplicates
    for col in ["Sector", "Industry", "Country"]:
        if f"{col}_analysis" in merged.columns:
            merged[col] = merged[f"{col}_analysis"].fillna(merged.get(f"{col}_screen", ""))
            merged = merged.drop(columns=[f"{col}_analysis", f"{col}_screen"], errors="ignore")

    return merged

