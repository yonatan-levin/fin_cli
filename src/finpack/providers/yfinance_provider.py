"""YFinance provider implementation using yfinance.

This provider adheres to the :class:`finpack.providers.base.Provider` contract.
"""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import yfinance as yf

from .base import Provider


class YFinanceProvider(Provider):
    """Provider backed by yfinance's Ticker API."""

    def get_info(self, symbol: str) -> Mapping[str, Any]:
        try:
            t = yf.Ticker(symbol)
            # yfinance exposes a full info dict
            return t.info or {}
        except Exception:
            # Network or backend errors should not propagate to callers
            return {}

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        try:
            t = yf.Ticker(symbol)
            df = t.history(period=period, interval=interval)
            return df.reset_index() if isinstance(df, pd.DataFrame) else pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        try:
            t = yf.Ticker(symbol)
            df = t.balance_sheet
            if not isinstance(df, pd.DataFrame) or df.empty:
                return pd.DataFrame()
            # Typical shape has rows as fields (index) and columns as dates; normalize
            if df.index.name is None and "Total Assets" in df.index:
                df = df.T
            # Standardize common column names used by analyzer
            rename_map = {
                "Total Assets": "TotalAssets",
                "Current Assets": "CurrentAssets",
            }
            df = df.rename(columns=rename_map)
            return df.reset_index(drop=True)
        except Exception:
            return pd.DataFrame()


