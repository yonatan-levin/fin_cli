"""
Data provider interfaces module.

This module defines the abstract interfaces for data providers
used in the fundainsight application.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

from ..models.financial_data import FinancialData
from ..models.stock import Stock, StockCollection


class StockDataProvider(ABC):
    """
    Abstract interface for stock data providers.
    
    This interface defines the contract that all stock data providers
    must implement to be used in the application.
    """
    
    @abstractmethod
    def get_stock(self, symbol: str) -> Stock:
        """
        Retrieve data for a single stock by symbol.
        
        Args:
            symbol: The stock ticker symbol
            
        Returns:
            Stock object with the requested data
            
        Raises:
            StockNotFoundError: If the stock symbol is not found
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass
    
    @abstractmethod
    def get_stocks(self, symbols: List[str]) -> StockCollection:
        """
        Retrieve data for multiple stocks by symbols.
        
        Args:
            symbols: List of stock ticker symbols
            
        Returns:
            StockCollection containing the requested stocks
            
        Raises:
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass
    
    @abstractmethod
    def search_stocks(self, query: str, limit: int = 10) -> StockCollection:
        """
        Search for stocks based on a query string.
        
        Args:
            query: Search query string
            limit: Maximum number of results to return
            
        Returns:
            StockCollection containing the search results
            
        Raises:
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass


class FinancialDataProvider(ABC):
    """
    Abstract interface for financial data providers.
    
    This interface defines the contract that all financial data providers
    must implement to be used in the application.
    """
    
    @abstractmethod
    def get_financial_data(self, symbol: str) -> FinancialData:
        """
        Retrieve financial data for a single stock by symbol.
        
        Args:
            symbol: The stock ticker symbol
            
        Returns:
            FinancialData object with the requested data
            
        Raises:
            StockNotFoundError: If the stock symbol is not found
            FinancialStatementError: If financial statements cannot be retrieved
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass
    
    @abstractmethod
    def get_balance_sheet(self, symbol: str, quarterly: bool = True) -> Dict[str, Any]:
        """
        Retrieve balance sheet data for a stock.
        
        Args:
            symbol: The stock ticker symbol
            quarterly: Whether to retrieve quarterly (True) or annual (False) data
            
        Returns:
            Dictionary containing balance sheet data
            
        Raises:
            StockNotFoundError: If the stock symbol is not found
            FinancialStatementError: If financial statements cannot be retrieved
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass
    
    @abstractmethod
    def get_income_statement(self, symbol: str, quarterly: bool = True) -> Dict[str, Any]:
        """
        Retrieve income statement data for a stock.
        
        Args:
            symbol: The stock ticker symbol
            quarterly: Whether to retrieve quarterly (True) or annual (False) data
            
        Returns:
            Dictionary containing income statement data
            
        Raises:
            StockNotFoundError: If the stock symbol is not found
            FinancialStatementError: If financial statements cannot be retrieved
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass
    
    @abstractmethod
    def get_cash_flow(self, symbol: str, quarterly: bool = True) -> Dict[str, Any]:
        """
        Retrieve cash flow data for a stock.
        
        Args:
            symbol: The stock ticker symbol
            quarterly: Whether to retrieve quarterly (True) or annual (False) data
            
        Returns:
            Dictionary containing cash flow data
            
        Raises:
            StockNotFoundError: If the stock symbol is not found
            FinancialStatementError: If financial statements cannot be retrieved
            FinancialDataRetrievalError: If there is an error retrieving the data
        """
        pass


class CacheProvider(ABC):
    """
    Abstract interface for cache providers.
    
    This interface defines the contract that all cache providers
    must implement to be used in the application.
    """
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from the cache by key.
        
        Args:
            key: Cache key
            
        Returns:
            The cached value, or None if not found
        """
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store a value in the cache.
        
        Args:
            key: Cache key
            value: Value to store
            ttl: Time-to-live in seconds (optional)
        """
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if the value was deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all values from the cache."""
        pass
    
    @abstractmethod
    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Retrieve multiple values from the cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dictionary mapping keys to values (missing keys are omitted)
        """
        pass
    
    @abstractmethod
    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Store multiple values in the cache.
        
        Args:
            mapping: Dictionary mapping keys to values
            ttl: Time-to-live in seconds (optional)
        """
        pass 