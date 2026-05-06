from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..providers.yfinance_provider import YFinanceProvider


class FundamentalAnalyzer:
    """Compute simple insights based on Yahoo data (via yfinance)."""

    def __init__(self, provider: YFinanceProvider | None = None) -> None:
        self.provider = provider or YFinanceProvider()

    def ratios(self, symbol: str) -> Dict[str, float | str]:
        """Compute fundamental ratios and descriptors for a symbol.

        Returns a dict with:
        - price_by_assets: Total assets per share
        - price_by_current_assets: Current assets per share
        - price/price_to_current_assets_ratio: 30-day median price / price_by_current_assets
        - price/price_to_assets_ratio: 30-day median price / price_by_assets
        - average_price_30d: 30-day median close price (if available)
        - market_cap: Market capitalization (if available)
        - sector: Company sector (if available)
        - industry: Company industry (if available)
        - country: Company country (if available)
        """
        balance = self.provider.get_balance_sheet(symbol)
        if balance.empty:
            return {}
        latest = balance.iloc[-1]
        total_assets = float(latest.get("TotalAssets") or latest.get("Total Assets") or 0)
        current_assets = float(latest.get("CurrentAssets") or latest.get("Current Assets") or 0)
        info = self.provider.get_info(symbol)
        shares_outstanding = float(info.get("sharesOutstanding", 0) or 0)
        market_cap = info.get("marketCap")

        # Compute 30-day median close price (used as numerator in ratios)
        avg_price_30d = None
        try:
            hist = self.provider.get_history(symbol, period="1mo", interval="1d")
            if isinstance(hist, pd.DataFrame) and "close" in hist.columns and not hist.empty:
                avg_price_30d = float(hist["close"].quantile(0.5))
        except Exception:
            avg_price_30d = None

        # Calculate per-share metrics
        price_by_assets = 0.0 if shares_outstanding == 0 else total_assets / shares_outstanding
        price_by_current_assets = 0.0 if shares_outstanding == 0 else current_assets / shares_outstanding

        # Calculate ratios using 30-day median price (not current price)
        if avg_price_30d is not None and avg_price_30d > 0:
            ratio_current = 0.0 if price_by_current_assets == 0 else avg_price_30d / price_by_current_assets
            ratio_assets = 0.0 if price_by_assets == 0 else avg_price_30d / price_by_assets
        else:
            # No historical price available; ratios default to zero
            ratio_current = 0.0
            ratio_assets = 0.0

        result: Dict[str, float | str] = {
            "price_by_assets": price_by_assets,
            "price_by_current_assets": price_by_current_assets,
            "price/price_to_current_assets_ratio": ratio_current,
            "price/price_to_assets_ratio": ratio_assets,
        }

        # Add optional fields when available
        if avg_price_30d is not None:
            result["average_price_30d"] = avg_price_30d
        if market_cap is not None:
            try:
                result["market_cap"] = float(market_cap)
            except Exception:
                pass

        # Extract sector, industry, country from info
        result["sector"] = info.get("sector", "")
        result["industry"] = info.get("industry", "")
        result["country"] = info.get("country", "")

        return result

    def ratios_batch(self, symbols: List[str]) -> pd.DataFrame:
        """Compute ratios for multiple symbols and return as DataFrame.

        Returns DataFrame with columns: Symbol, price_by_assets, price_by_current_assets,
        price/price_to_current_assets_ratio, price/price_to_assets_ratio,
        average_price_30d (optional), market_cap (optional), sector, industry, country.
        """
        rows: List[Dict[str, float | str]] = []
        for sym in symbols:
            r = self.ratios(sym)
            if r:
                rows.append({"Symbol": sym, **r})
        return pd.DataFrame(rows)
