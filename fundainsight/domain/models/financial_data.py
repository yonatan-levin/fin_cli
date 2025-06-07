"""
Financial data domain model.

This module defines the FinancialData entity and related value objects that represent
financial statements and metrics for stocks in the fundainsight application.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class BalanceSheet:
    """
    Balance sheet data for a company.
    
    Represents the financial position of a company at a specific point in time.
    
    Attributes:
        total_assets: Total assets value
        current_assets: Current assets value
        inventory: Inventory value
        goodwill: Goodwill value
        other_current_assets: Other current assets value
        other_non_current_assets: Other non-current assets value
        total_liabilities: Total liabilities value
        stockholders_equity: Stockholders' equity value
        date: Date of the balance sheet
    """
    total_assets: float
    stockholders_equity: float
    date: str
    current_assets: Optional[float] = None
    inventory: Optional[float] = None
    goodwill: Optional[float] = None
    other_current_assets: Optional[float] = None
    other_non_current_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    
    def __post_init__(self):
        """Validate the balance sheet data after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate the balance sheet data."""
        if self.total_assets < 0:
            raise ValueError("Total assets cannot be negative")
        
        if self.stockholders_equity < 0:
            raise ValueError("Stockholders equity cannot be negative")
            
        # Validate optional fields if provided
        if self.current_assets is not None and self.current_assets < 0:
            raise ValueError("Current assets cannot be negative")
            
        if self.inventory is not None and self.inventory < 0:
            raise ValueError("Inventory cannot be negative")
            
        if self.goodwill is not None and self.goodwill < 0:
            raise ValueError("Goodwill cannot be negative")
            
        if self.total_liabilities is not None and self.total_liabilities < 0:
            raise ValueError("Total liabilities cannot be negative")


@dataclass
class FinancialData:
    """
    Financial data for a company.
    
    Represents comprehensive financial information for a company,
    including balance sheet, calculated metrics, and other financial data.
    
    Attributes:
        symbol: The ticker symbol of the stock
        sector: The sector of the stock
        industry: The industry of the stock
        country: The country of the stock
        market_cap: Market capitalization
        shares_outstanding: Number of outstanding shares
        average_price_30d: Average price in the last 30 days
        balance_sheet: Balance sheet data
        adjusted_total_assets: Total assets adjusted for goodwill and other items
        adjusted_current_assets: Current assets adjusted for certain items
        price_to_assets_ratio: Price to assets ratio
        price_to_current_assets_ratio: Price to current assets ratio
    """
    symbol: str
    sector: str
    industry: str
    country: str
    market_cap: float
    shares_outstanding: int
    average_price_30d: float
    balance_sheet: BalanceSheet
    adjusted_total_assets: Optional[float] = None
    adjusted_current_assets: Optional[float] = None
    price_to_assets_ratio: Optional[float] = None
    price_to_current_assets_ratio: Optional[float] = None
    
    def __post_init__(self):
        """Calculate derived metrics and validate data."""
        self._calculate_derived_metrics()
        self._validate()
    
    def _calculate_derived_metrics(self):
        """Calculate derived financial metrics."""
        # Calculate metrics if not already set
        if self.adjusted_total_assets is None:
            self.adjusted_total_assets = self._adjust_total_assets()
            
        if self.adjusted_current_assets is None:
            self.adjusted_current_assets = self._adjust_current_assets()
            
        if self.price_to_assets_ratio is None and self.adjusted_total_assets:
            self.price_to_assets_ratio = self._calculate_price_to_data(self.adjusted_total_assets)
            
        if self.price_to_current_assets_ratio is None and self.adjusted_current_assets:
            self.price_to_current_assets_ratio = self._calculate_price_to_data(self.adjusted_current_assets)
    
    def _adjust_total_assets(self) -> float:
        """
        Adjust total assets by removing goodwill and other non-current assets.
        
        Returns:
            Adjusted total assets value
        """
        adjusted = self.balance_sheet.total_assets
        
        # Subtract goodwill if available
        if self.balance_sheet.goodwill is not None:
            adjusted -= self.balance_sheet.goodwill
            
        # Subtract other non-current assets if available
        if self.balance_sheet.other_non_current_assets is not None:
            adjusted -= self.balance_sheet.other_non_current_assets
            
        return max(0, adjusted)  # Ensure non-negative
    
    def _adjust_current_assets(self) -> float:
        """
        Adjust current assets by applying a discount to inventory and removing other current assets.
        
        Returns:
            Adjusted current assets value
        """
        if self.balance_sheet.current_assets is None:
            return 0
            
        adjusted = self.balance_sheet.current_assets
        
        # Apply inventory adjustment if available (30% discount)
        if self.balance_sheet.inventory is not None:
            adjusted += (0.3 * self.balance_sheet.inventory)
            
        # Subtract other current assets if available
        if self.balance_sheet.other_current_assets is not None:
            adjusted -= self.balance_sheet.other_current_assets
            
        return max(0, adjusted)  # Ensure non-negative
    
    def _calculate_price_to_data(self, value: float) -> float:
        """
        Calculate price to data ratio.
        
        Args:
            value: The financial data value to use in the calculation
            
        Returns:
            Price to data ratio
        """
        if value == 0 or self.shares_outstanding == 0:
            return 0
        return value / self.shares_outstanding
    
    def _validate(self):
        """Validate the financial data."""
        if not self.symbol:
            raise ValueError("Symbol cannot be empty")
            
        if self.market_cap < 0:
            raise ValueError("Market cap cannot be negative")
            
        if self.shares_outstanding <= 0:
            raise ValueError("Shares outstanding must be positive")
            
        if self.average_price_30d < 0:
            raise ValueError("Average price cannot be negative")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FinancialData':
        """
        Create a FinancialData instance from a dictionary.
        
        Args:
            data: Dictionary containing financial data
            
        Returns:
            A new FinancialData instance
        """
        # Extract balance sheet data
        balance_sheet = BalanceSheet(
            total_assets=data.get('Total Assets', 0),
            stockholders_equity=data.get('Total Equity', 0),
            date=data.get('Date', ''),
            current_assets=data.get('Current Assets'),
            inventory=data.get('Inventory'),
            goodwill=data.get('Goodwill'),
            other_current_assets=data.get('Other Current Assets'),
            other_non_current_assets=data.get('Other Non Current Assets'),
            total_liabilities=data.get('Total Liabilities')
        )
        
        return cls(
            symbol=data.get('Ticker', ''),
            sector=data.get('Sector', ''),
            industry=data.get('Industry', ''),
            country=data.get('Country', ''),
            market_cap=data.get('Market Cap', 0),
            shares_outstanding=data.get('Shares Outstanding', 0),
            average_price_30d=data.get('Average Price in Last 30 Days', 0),
            balance_sheet=balance_sheet,
            adjusted_total_assets=data.get('Adjusted Total Assets'),
            adjusted_current_assets=data.get('Adjusted Total Current Assets'),
            price_to_assets_ratio=data.get('price/price_to_assets_ratio'),
            price_to_current_assets_ratio=data.get('price/price_to_current_assets_ratio')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the FinancialData to a dictionary.
        
        Returns:
            Dictionary representation of the FinancialData
        """
        return {
            'Ticker': self.symbol,
            'Sector': self.sector,
            'Industry': self.industry,
            'Country': self.country,
            'Market Cap': self.market_cap,
            'Shares Outstanding': self.shares_outstanding,
            'Average Price in Last 30 Days': self.average_price_30d,
            'Total Assets': self.balance_sheet.total_assets,
            'Total Equity': self.balance_sheet.stockholders_equity,
            'Adjusted Total Assets': self.adjusted_total_assets,
            'Adjusted Total Current Assets': self.adjusted_current_assets,
            'price/price_to_assets_ratio': self.price_to_assets_ratio,
            'price/price_to_current_assets_ratio': self.price_to_current_assets_ratio
        } 