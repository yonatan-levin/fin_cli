"""DEPRECATED: Old pipeline module.

This module is deprecated. Use the new two-step API instead:
- finpack.screen() for screening
- finpack.analyze() for fundamental analysis
- finpack.enrich() for combining results

See examples/advanced_usage.py for the new workflow.
"""

from __future__ import annotations

import warnings
import pandas as pd

from .analyzer import FundamentalAnalyzer


def build_unfiltered_results(symbols: list[str], analyzer: FundamentalAnalyzer | None = None) -> pd.DataFrame:
    """DEPRECATED: Use finpack.analyze() instead.

    This function is deprecated and maintained only for backward compatibility.
    New code should use finpack.analyze(symbols) which provides the same functionality
    with better column handling and descriptors (sector, industry, country).

    Columns: Ticker, Sector, Industry, Country, Market Cap, Average Price in Last 30 Days,
             price_by_assets, price_by_current_assets, price/price_to_current_assets_ratio,
             price/price_to_assets_ratio
    """
    warnings.warn(
        "build_unfiltered_results() is deprecated. Use finpack.analyze(symbols) instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    # Delegate to new API for consistent behavior
    from ..api import analyze
    return analyze(symbols)


