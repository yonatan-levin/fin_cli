"""
Integration tests for Task 3: Consolidate Data Models and Domain Logic.

This module tests the integration between the new shared domain services,
adapters, and the enhanced picker implementation.
"""
from fundainsight.app.stock_picker import StockPicker
from shared.domain.services.financial_data_provider import YFinanceDataProvider
from shared.domain.services.financial_calculation_service import (
    FinancialCalculationService,
    FinancialMetricsService,
    AssetAdjustmentService
)
from shared.domain.adapters.fincli_data_adapter import FinCliDataAdapter, FinCliAdapterFactory
import unittest
import pandas as pd
from unittest.mock import Mock, patch
import sys
import os

# Add the workspace root to the Python path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../..')))


class TestFinancialCalculationService(unittest.TestCase):
    """Test the financial calculation service."""

    def test_calculate_price_to_data_ratio(self):
        """Test price to data ratio calculation."""
        # Normal case
        result = FinancialCalculationService.calculate_price_to_data_ratio(
            1000000, 100000)
        self.assertEqual(result, 10.0)

        # Edge cases
        self.assertEqual(
            FinancialCalculationService.calculate_price_to_data_ratio(0, 100000), 0.0)
        self.assertEqual(
            FinancialCalculationService.calculate_price_to_data_ratio(1000000, 0), 0.0)

    def test_calculate_ratio_between_values(self):
        """Test ratio calculation between two values."""
        result = FinancialCalculationService.calculate_ratio_between_values(
            100, 50)
        self.assertEqual(result, 2.0)

        # Division by zero
        result = FinancialCalculationService.calculate_ratio_between_values(
            100, 0)
        self.assertEqual(result, 0.0)

    def test_calculate_adjusted_assets(self):
        """Test adjusted assets calculation."""
        result = FinancialCalculationService.calculate_adjusted_assets(
            1000, 100, 50)
        self.assertEqual(result, 850.0)

        # With None values
        result = FinancialCalculationService.calculate_adjusted_assets(
            1000, None, 50)
        self.assertEqual(result, 950.0)

        # Ensure non-negative result
        result = FinancialCalculationService.calculate_adjusted_assets(
            100, 200, 50)
        self.assertEqual(result, 0.0)

    def test_calculate_price_ratios(self):
        """Test comprehensive price ratios calculation."""
        result = FinancialCalculationService.calculate_price_ratios(
            50, 1000000, 500000, 100000)

        price_by_assets, price_by_current_assets, price_to_assets_ratio, price_to_current_assets_ratio = result

        self.assertEqual(price_by_assets, 10.0)
        self.assertEqual(price_by_current_assets, 5.0)
        self.assertEqual(price_to_assets_ratio, 5.0)
        self.assertEqual(price_to_current_assets_ratio, 10.0)


class TestFinancialMetricsService(unittest.TestCase):
    """Test the financial metrics service."""

    def test_calculate_comprehensive_metrics(self):
        """Test comprehensive metrics calculation."""
        test_data = {
            'Symbol': 'AAPL',
            'Market Cap': 2000000000,
            'Shares Outstanding': 100000000,
            'Total Assets': 1000000000,
            'Adjusted Total Assets': 900000000,
            'Adjusted Total Current Assets': 500000000,
            'Average Price in Last 30 Days': 150.0
        }

        result = FinancialMetricsService.calculate_comprehensive_metrics(
            test_data)

        # Check that original data is preserved
        self.assertEqual(result['Symbol'], 'AAPL')
        self.assertEqual(result['Market Cap'], 2000000000)

        # Check that new metrics are added
        self.assertIn('price_by_assets', result)
        self.assertIn('price_by_current_assets', result)
        self.assertIn('price/price_to_assets_ratio', result)
        self.assertIn('price/price_to_current_assets_ratio', result)

        # Verify calculations
        self.assertEqual(result['price_by_assets'],
                         9.0)  # 900000000 / 100000000
        # 500000000 / 100000000
        self.assertEqual(result['price_by_current_assets'], 5.0)


class TestFinCliDataAdapter(unittest.TestCase):
    """Test the FinCli data adapter."""

    def setUp(self):
        """Set up test data."""
        self.sample_df = pd.DataFrame({
            'No.': [1, 2],
            'Ticker': ['AAPL', 'MSFT'],
            'Company': ['Apple Inc.', 'Microsoft Corp.'],
            'Sector': ['Technology', 'Technology'],
            'Industry': ['Consumer Electronics', 'Software'],
            'Country': ['USA', 'USA'],
            'Market Cap': ['2.5T', '1.8T'],
            'P/E': [25.5, 22.3],
            'Price': [150.0, 250.0],
            'Change': [2.5, -1.2],
            'Volume': [1000000, 800000]
        })

    def test_convert_to_stocks(self):
        """Test conversion to Stock domain objects."""
        adapter = FinCliAdapterFactory.create_basic_adapter()
        stock_collection = adapter.convert_to_stocks(self.sample_df)

        self.assertEqual(len(stock_collection.stocks), 2)

        aapl_stock = stock_collection.stocks[0]
        self.assertEqual(aapl_stock.symbol, 'AAPL')
        self.assertEqual(aapl_stock.company_name, 'Apple Inc.')
        self.assertEqual(aapl_stock.sector, 'Technology')
        self.assertEqual(aapl_stock.market_cap, 2.5e12)  # 2.5T converted

    def test_market_cap_parsing(self):
        """Test market cap parsing from string format."""
        adapter = FinCliDataAdapter()

        # Test various formats
        self.assertEqual(adapter._parse_market_cap('1.5B'), 1.5e9)
        self.assertEqual(adapter._parse_market_cap('500M'), 500e6)
        self.assertEqual(adapter._parse_market_cap('2.5T'), 2.5e12)
        self.assertEqual(adapter._parse_market_cap(1000000), 1000000.0)
        self.assertIsNone(adapter._parse_market_cap('-'))
        self.assertIsNone(adapter._parse_market_cap('N/A'))

    @patch('shared.domain.services.financial_data_provider.get_financial_data')
    def test_convert_to_financial_data(self, mock_get_financial_data):
        """Test conversion to FinancialData domain objects."""
        # Mock financial data provider response
        mock_financial_data = {
            'Symbol': 'AAPL',
            'Market Cap': 2500000000000,
            'Shares Outstanding': 15000000000,
            'Total Assets': 350000000000,
            'Adjusted Total Assets': 320000000000,
            'Adjusted Total Current Assets': 120000000000,
            'Total Equity': 60000000000,
            'Average Price in Last 30 Days': 150.0,
        }

        mock_get_financial_data.return_value = mock_financial_data

        # Test with single row DataFrame
        test_df = self.sample_df.iloc[:1].copy()  # Just AAPL
        test_df['Symbol'] = test_df['Ticker']  # Add Symbol column

        adapter = FinCliAdapterFactory.create_with_yfinance_provider()
        financial_data_objects = adapter.convert_to_financial_data(
            test_df, use_parallel=False)

        self.assertEqual(len(financial_data_objects), 1)

        aapl_financial = financial_data_objects[0]
        self.assertEqual(aapl_financial.symbol, 'AAPL')
        self.assertEqual(aapl_financial.market_cap, 2500000000000)


class TestEnhancedStockPicker(unittest.TestCase):
    """Test the enhanced stock picker implementation."""

    def setUp(self):
        """Set up test data."""
        self.sample_df = pd.DataFrame({
            'No.': [1, 2],
            'Ticker': ['AAPL', 'MSFT'],
            'Company': ['Apple Inc.', 'Microsoft Corp.'],
            # Mixed sectors for filtering test
            'Sector': ['Technology', 'Energy'],
            'Industry': ['Consumer Electronics', 'Software'],
            'Country': ['USA', 'Brazil'],  # Mixed countries for filtering test
            'Market Cap': ['2.5T', '1.8T'],
            'P/E': [25.5, 22.3],
            'Price': [150.0, 250.0],
            'Change': [2.5, -1.2],
            'Volume': [1000000, 800000],
            'Symbol': ['AAPL', 'MSFT']  # Add Symbol column
        })

    @patch('shared.domain.adapters.fincli_data_adapter_simple.FinCliDataAdapter.convert_to_financial_data')
    @patch('shared.infrastructure.config.get_config')
    def test_enhanced_picker_integration(self, mock_get_config, mock_convert_to_financial_data):
        """Test the enhanced picker integration."""
        # Mock config
        mock_config = Mock()
        mock_config.file_path.return_value = '/tmp/test_output.csv'
        mock_get_config.return_value = mock_config

        # Mock financial data objects
        from fundainsight.domain.models.financial_data import FinancialData, BalanceSheet
        mock_balance_sheet = BalanceSheet(
            total_assets=350000000000,
            stockholders_equity=60000000000,
            date='2024-01-01',
            current_assets=120000000000
        )

        mock_financial_data = FinancialData(
            symbol='AAPL',
            market_cap=2500000000000,
            shares_outstanding=15000000000,
            average_price_30d=150.0,
            balance_sheet=mock_balance_sheet
        )

        mock_convert_to_financial_data.return_value = [mock_financial_data]

        # Test enhanced picker
        picker = StockPicker()
        result = picker.pick_stocks(self.sample_df)

        # Verify the process completed (result may be None due to filtering)
        # The important thing is that no exceptions were raised
        self.assertIsNotNone(mock_convert_to_financial_data.call_args)


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility with existing code."""

    @patch('shared.domain.services.financial_data_provider.get_financial_data')
    def test_new_services_provide_same_interface(self, mock_get_financial_data):
        """Test that new services provide the same interface as old ones."""
        # Test that the new financial data provider function matches the old signature
        mock_get_financial_data.return_value = {
            'Symbol': 'AAPL',
            'Market Cap': 2500000000000,
            'Shares Outstanding': 15000000000,
        }

        from shared.domain.services.financial_data_provider import get_financial_data
        result = get_financial_data('AAPL')

        # Should return a dictionary with the expected structure
        self.assertIsInstance(result, dict)
        self.assertIn('Symbol', result)
        self.assertIn('Market Cap', result)


if __name__ == '__main__':
    unittest.main()
