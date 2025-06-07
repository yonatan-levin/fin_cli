"""
Stock domain model.

This module defines the Stock entity and related value objects that represent
the core domain model for stocks in the fundainsight application.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List


@dataclass
class Stock:
    """
    Stock domain entity representing a publicly traded company.
    
    This class encapsulates all the properties and behaviors of a stock
    that are relevant to the business domain, independent of any specific
    data source or presentation concerns.
    
    Attributes:
        symbol: The ticker symbol of the stock (e.g., 'AAPL')
        company_name: The name of the company
        sector: The sector the company belongs to
        industry: The specific industry within the sector
        country: The country where the company is based
        market_cap: The market capitalization in USD
        shares_outstanding: Number of outstanding shares
        price: Current price of the stock
        price_history: Optional historical price data
    """
    symbol: str
    company_name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    market_cap: Optional[float] = None
    shares_outstanding: Optional[int] = None
    price: Optional[float] = None
    price_history: Optional[Dict[datetime, float]] = None
    
    def __post_init__(self):
        """Validate the stock data after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate the stock data."""
        if not self.symbol:
            raise ValueError("Stock symbol cannot be empty")
        
        if not isinstance(self.symbol, str):
            raise TypeError("Stock symbol must be a string")
        
        # Convert symbol to uppercase
        self.symbol = self.symbol.upper()
        
        # Validate market cap if provided
        if self.market_cap is not None and self.market_cap < 0:
            raise ValueError("Market cap cannot be negative")
        
        # Validate shares outstanding if provided
        if self.shares_outstanding is not None and self.shares_outstanding <= 0:
            raise ValueError("Shares outstanding must be positive")
        
        # Validate price if provided
        if self.price is not None and self.price < 0:
            raise ValueError("Price cannot be negative")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Stock':
        """
        Create a Stock instance from a dictionary.
        
        Args:
            data: Dictionary containing stock data
            
        Returns:
            A new Stock instance
        """
        # Extract known fields, ignore unknown ones
        return cls(
            symbol=data.get('Symbol', ''),
            company_name=data.get('Company Name', ''),
            sector=data.get('Sector'),
            industry=data.get('Industry'),
            country=data.get('Country'),
            market_cap=data.get('Market Cap'),
            shares_outstanding=data.get('Shares Outstanding'),
            price=data.get('Average Price in Last 30 Days')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the Stock to a dictionary.
        
        Returns:
            Dictionary representation of the Stock
        """
        return {
            'Symbol': self.symbol,
            'Company Name': self.company_name,
            'Sector': self.sector,
            'Industry': self.industry,
            'Country': self.country,
            'Market Cap': self.market_cap,
            'Shares Outstanding': self.shares_outstanding,
            'Price': self.price
        }


@dataclass
class StockCollection:
    """
    Collection of Stock entities.
    
    This class provides utilities for working with multiple stocks.
    
    Attributes:
        stocks: List of Stock entities
    """
    stocks: List[Stock]
    
    def filter_by_sector(self, sector: str) -> 'StockCollection':
        """
        Filter stocks by sector.
        
        Args:
            sector: Sector to filter by
            
        Returns:
            A new StockCollection with filtered stocks
        """
        filtered_stocks = [
            stock for stock in self.stocks 
            if stock.sector and stock.sector.lower() == sector.lower()
        ]
        return StockCollection(stocks=filtered_stocks)
    
    def filter_by_country(self, countries: List[str]) -> 'StockCollection':
        """
        Filter stocks by country.
        
        Args:
            countries: List of countries to include
            
        Returns:
            A new StockCollection with filtered stocks
        """
        countries_lower = [country.lower() for country in countries]
        filtered_stocks = [
            stock for stock in self.stocks 
            if stock.country and stock.country.lower() in countries_lower
        ]
        return StockCollection(stocks=filtered_stocks)
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Convert the collection to a list of dictionaries.
        
        Returns:
            List of dictionaries representing stocks
        """
        return [stock.to_dict() for stock in self.stocks] 