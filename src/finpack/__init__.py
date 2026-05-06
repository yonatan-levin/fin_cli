"""FinPack unified library public API.

This package provides stock screening using Finviz and fundamental insights
based on Yahoo Finance via yfinance.

Simple two-step API:
- screen(): Filter stocks using Finviz screener
- analyze(): Compute fundamental ratios for symbols
- enrich(): Merge screening and analysis results

Example:
    >>> import finpack
    >>> # Step 1: Screen stocks
    >>> screen_df = finpack.screen(filters=[("cap", "midover"), ("fa_pe", "u40")])
    >>> # Step 2: Analyze fundamentals
    >>> analysis_df = finpack.analyze(["AAPL", "MSFT", "GOOGL"])
"""

from .api import screen, analyze, enrich
from .core.screener import StockScreener
from .core.analyzer import FundamentalAnalyzer
from .providers.yfinance_provider import YFinanceProvider

__all__ = [
    # Primary two-step API
    "screen",
    "analyze",
    "enrich",
    # Core classes (for advanced usage)
    "StockScreener",
    "FundamentalAnalyzer",
    "YFinanceProvider",
]


