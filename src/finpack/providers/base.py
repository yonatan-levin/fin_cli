"""Provider base interfaces for finpack data access.

Defines abstract contracts for market data providers to implement a common API
compatible with the planned yfinance-style facades.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, Mapping, Optional

import pandas as pd


class Provider(ABC):
    """Abstract provider interface for market data and fundamentals."""

    @abstractmethod
    def get_info(self, symbol: str) -> Mapping[str, Any]:
        """Return static/info data for a single symbol."""

    @abstractmethod
    def get_history(
        self, symbol: str, period: str = "1y", interval: str = "1d"
    ) -> pd.DataFrame:
        """Return historical price data for a symbol."""

    @abstractmethod
    def get_balance_sheet(self, symbol: str) -> pd.DataFrame:
        """Return the latest balance sheet for a symbol."""

    # Optional batch APIs
    def get_info_batch(self, symbols: Iterable[str]) -> Dict[str, Mapping[str, Any]]:
        return {symbol: self.get_info(symbol) for symbol in symbols}

    def get_history_batch(
        self, symbols: Iterable[str], period: str = "1y", interval: str = "1d"
    ) -> Dict[str, pd.DataFrame]:
        return {symbol: self.get_history(symbol, period, interval) for symbol in symbols}

    def get_balance_sheet_batch(self, symbols: Iterable[str]) -> Dict[str, pd.DataFrame]:
        return {symbol: self.get_balance_sheet(symbol) for symbol in symbols}


