"""Yahoo Finance provider implementation using yahooquery.

This provider adheres to the :class:`finpack.providers.base.Provider` contract.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
from yahooquery import Ticker as YqTicker

from .base import Provider


class YahooProvider(Provider):
    """Provider backed by yahooquery's Ticker API."""

    def get_info(self, symbol: str) -> Mapping[str, Any]:
        t = YqTicker(symbol)
        # yahooquery returns dict keyed by symbol when passing a list; for single
        # symbol, it exposes attributes directly. Use .price/.summary_profile etc.
        price = t.price
        if isinstance(price, dict) and symbol in price:
            return price[symbol]
        return price

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        t = YqTicker(symbol)
        df = t.history(period=period, interval=interval)
        # yahooquery returns multi-index when multiple symbols; for single symbol it
        # still may include a symbol level. Normalize index and ensure a clean frame.
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()
        if isinstance(df.index, pd.MultiIndex):
            # drop the symbol level if present
            if 'symbol' in df.index.names:
                df = df.reset_index(level='symbol', drop=True)
        return df.reset_index()

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        t = YqTicker(symbol)
        df = t.balance_sheet()
        if not isinstance(df, pd.DataFrame):
            return pd.DataFrame()
        # Normalize possible multi-index
        return df.reset_index(drop=True)


