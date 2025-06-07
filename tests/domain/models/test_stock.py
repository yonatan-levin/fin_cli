"""
Unit tests for Stock domain model.
"""
import unittest
from datetime import datetime
from typing import Dict, List

from fundainsight.domain.models.stock import Stock, StockCollection


class TestStock(unittest.TestCase):
    """Test cases for the Stock class."""

    def test_stock_initialization(self):
        """Test initializing a Stock with valid data."""
        # Arrange & Act
        stock = Stock(
            symbol="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            country="USA",
            market_cap=2500000000000,
            shares_outstanding=16000000000,
            price=155.75
        )
        
        # Assert
        self.assertEqual(stock.symbol, "AAPL")
        self.assertEqual(stock.company_name, "Apple Inc.")
        self.assertEqual(stock.sector, "Technology")
        self.assertEqual(stock.industry, "Consumer Electronics")
        self.assertEqual(stock.country, "USA")
        self.assertEqual(stock.market_cap, 2500000000000)
        self.assertEqual(stock.shares_outstanding, 16000000000)
        self.assertEqual(stock.price, 155.75)
    
    def test_stock_symbol_validation(self):
        """Test that Stock validates the symbol."""
        # Empty symbol
        with self.assertRaises(ValueError):
            Stock(symbol="", company_name="Test Company")
        
        # Non-string symbol
        with self.assertRaises(TypeError):
            Stock(symbol=123, company_name="Test Company")  # type: ignore
    
    def test_stock_uppercase_symbol(self):
        """Test that Stock converts the symbol to uppercase."""
        # Arrange & Act
        stock = Stock(symbol="aapl", company_name="Apple Inc.")
        
        # Assert
        self.assertEqual(stock.symbol, "AAPL")
    
    def test_stock_validation_market_cap(self):
        """Test that Stock validates market_cap."""
        # Negative market cap
        with self.assertRaises(ValueError):
            Stock(
                symbol="AAPL",
                company_name="Apple Inc.",
                market_cap=-1000000
            )
    
    def test_stock_validation_shares_outstanding(self):
        """Test that Stock validates shares_outstanding."""
        # Zero shares outstanding
        with self.assertRaises(ValueError):
            Stock(
                symbol="AAPL",
                company_name="Apple Inc.",
                shares_outstanding=0
            )
        
        # Negative shares outstanding
        with self.assertRaises(ValueError):
            Stock(
                symbol="AAPL",
                company_name="Apple Inc.",
                shares_outstanding=-1000
            )
    
    def test_stock_validation_price(self):
        """Test that Stock validates price."""
        # Negative price
        with self.assertRaises(ValueError):
            Stock(
                symbol="AAPL",
                company_name="Apple Inc.",
                price=-100.00
            )
    
    def test_stock_from_dict(self):
        """Test creating a Stock from a dictionary."""
        # Arrange
        data = {
            "Symbol": "AAPL",
            "Company Name": "Apple Inc.",
            "Sector": "Technology",
            "Industry": "Consumer Electronics",
            "Country": "USA",
            "Market Cap": 2500000000000,
            "Shares Outstanding": 16000000000,
            "Average Price in Last 30 Days": 155.75
        }
        
        # Act
        stock = Stock.from_dict(data)
        
        # Assert
        self.assertEqual(stock.symbol, "AAPL")
        self.assertEqual(stock.company_name, "Apple Inc.")
        self.assertEqual(stock.sector, "Technology")
        self.assertEqual(stock.industry, "Consumer Electronics")
        self.assertEqual(stock.country, "USA")
        self.assertEqual(stock.market_cap, 2500000000000)
        self.assertEqual(stock.shares_outstanding, 16000000000)
        self.assertEqual(stock.price, 155.75)
    
    def test_stock_to_dict(self):
        """Test converting a Stock to a dictionary."""
        # Arrange
        stock = Stock(
            symbol="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            country="USA",
            market_cap=2500000000000,
            shares_outstanding=16000000000,
            price=155.75
        )
        
        # Act
        data = stock.to_dict()
        
        # Assert
        self.assertEqual(data["Symbol"], "AAPL")
        self.assertEqual(data["Company Name"], "Apple Inc.")
        self.assertEqual(data["Sector"], "Technology")
        self.assertEqual(data["Industry"], "Consumer Electronics")
        self.assertEqual(data["Country"], "USA")
        self.assertEqual(data["Market Cap"], 2500000000000)
        self.assertEqual(data["Shares Outstanding"], 16000000000)
        self.assertEqual(data["Price"], 155.75)


class TestStockCollection(unittest.TestCase):
    """Test cases for the StockCollection class."""
    
    def setUp(self):
        """Set up test data."""
        self.stocks = [
            Stock(
                symbol="AAPL",
                company_name="Apple Inc.",
                sector="Technology",
                industry="Consumer Electronics",
                country="USA",
                market_cap=2500000000000,
                shares_outstanding=16000000000,
                price=155.75
            ),
            Stock(
                symbol="MSFT",
                company_name="Microsoft Corporation",
                sector="Technology",
                industry="Software",
                country="USA",
                market_cap=2000000000000,
                shares_outstanding=7500000000,
                price=280.33
            ),
            Stock(
                symbol="BABA",
                company_name="Alibaba Group Holding Ltd",
                sector="Consumer Cyclical",
                industry="Internet Retail",
                country="China",
                market_cap=230000000000,
                shares_outstanding=2600000000,
                price=88.09
            ),
            Stock(
                symbol="VALE",
                company_name="Vale S.A.",
                sector="Basic Materials",
                industry="Metals & Mining",
                country="Brazil",
                market_cap=70000000000,
                shares_outstanding=4600000000,
                price=15.22
            )
        ]
        self.collection = StockCollection(stocks=self.stocks)
    
    def test_filter_by_sector(self):
        """Test filtering stocks by sector."""
        # Act
        tech_stocks = self.collection.filter_by_sector("Technology")
        
        # Assert
        self.assertEqual(len(tech_stocks.stocks), 2)
        self.assertEqual(tech_stocks.stocks[0].symbol, "AAPL")
        self.assertEqual(tech_stocks.stocks[1].symbol, "MSFT")
    
    def test_filter_by_sector_case_insensitive(self):
        """Test that filtering by sector is case-insensitive."""
        # Act
        tech_stocks = self.collection.filter_by_sector("technology")
        
        # Assert
        self.assertEqual(len(tech_stocks.stocks), 2)
    
    def test_filter_by_sector_no_match(self):
        """Test filtering by a sector with no matches."""
        # Act
        energy_stocks = self.collection.filter_by_sector("Energy")
        
        # Assert
        self.assertEqual(len(energy_stocks.stocks), 0)
    
    def test_filter_by_country(self):
        """Test filtering stocks by country."""
        # Act
        us_stocks = self.collection.filter_by_country(["USA"])
        
        # Assert
        self.assertEqual(len(us_stocks.stocks), 2)
        self.assertEqual(us_stocks.stocks[0].symbol, "AAPL")
        self.assertEqual(us_stocks.stocks[1].symbol, "MSFT")
    
    def test_filter_by_multiple_countries(self):
        """Test filtering stocks by multiple countries."""
        # Act
        emerging_stocks = self.collection.filter_by_country(["China", "Brazil"])
        
        # Assert
        self.assertEqual(len(emerging_stocks.stocks), 2)
        self.assertEqual(emerging_stocks.stocks[0].symbol, "BABA")
        self.assertEqual(emerging_stocks.stocks[1].symbol, "VALE")
    
    def test_filter_by_country_case_insensitive(self):
        """Test that filtering by country is case-insensitive."""
        # Act
        us_stocks = self.collection.filter_by_country(["usa"])
        
        # Assert
        self.assertEqual(len(us_stocks.stocks), 2)
    
    def test_to_dict_list(self):
        """Test converting the collection to a list of dictionaries."""
        # Act
        dict_list = self.collection.to_dict_list()
        
        # Assert
        self.assertEqual(len(dict_list), 4)
        self.assertEqual(dict_list[0]["Symbol"], "AAPL")
        self.assertEqual(dict_list[1]["Symbol"], "MSFT")
        self.assertEqual(dict_list[2]["Symbol"], "BABA")
        self.assertEqual(dict_list[3]["Symbol"], "VALE")


if __name__ == "__main__":
    unittest.main() 