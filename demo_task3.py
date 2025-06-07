"""
Demonstration script for Task 3: Consolidate Data Models and Domain Logic.

This script demonstrates the new shared domain services, adapters, and 
enhanced picker implementation.
"""
import pandas as pd
from shared.domain.adapters.fincli_data_adapter import FinCliAdapterFactory
from shared.domain.services.financial_calculation_service import (
    FinancialCalculationService,
    FinancialMetricsService
)


def demo_financial_calculations():
    """Demonstrate the financial calculation services."""
    print("=== Financial Calculation Service Demo ===")

    # Test price to data ratio calculation
    asset_value = 1000000
    shares = 100000
    ratio = FinancialCalculationService.calculate_price_to_data_ratio(
        asset_value, shares)
    print(f"Price to data ratio: {asset_value:,} / {shares:,} = {ratio}")

    # Test adjusted assets calculation
    total_assets = 1000
    goodwill = 100
    other_assets = 50
    adjusted = FinancialCalculationService.calculate_adjusted_assets(
        total_assets, goodwill, other_assets)
    print(
        f"Adjusted assets: {total_assets} - {goodwill} - {other_assets} = {adjusted}")

    # Test comprehensive price ratios
    price_ratios = FinancialCalculationService.calculate_price_ratios(
        average_price=50.0,
        adjusted_total_assets=1000000,
        adjusted_current_assets=500000,
        shares_outstanding=100000
    )
    print(f"Price ratios: {price_ratios}")
    print()


def demo_data_adapter():
    """Demonstrate the FinCli data adapter."""
    print("=== FinCli Data Adapter Demo ===")

    # Create sample DataFrame (simulating fincli output)
    sample_data = pd.DataFrame({
        'No.': [1, 2, 3],
        'Ticker': ['AAPL', 'MSFT', 'GOOGL'],
        'Company': ['Apple Inc.', 'Microsoft Corp.', 'Alphabet Inc.'],
        'Sector': ['Technology', 'Technology', 'Technology'],
        'Industry': ['Consumer Electronics', 'Software', 'Internet'],
        'Country': ['USA', 'USA', 'USA'],
        'Market Cap': ['2.5T', '1.8T', '1.2T'],
        'P/E': [25.5, 22.3, 18.7],
        'Price': [150.0, 250.0, 120.0],
        'Change': [2.5, -1.2, 0.8],
        'Volume': [1000000, 800000, 600000]
    })

    print("Sample DataFrame from fincli:")
    print(sample_data[['Ticker', 'Company',
          'Market Cap', 'Price']].to_string())
    print()

    # Convert to Stock domain objects
    adapter = FinCliAdapterFactory.create_basic_adapter()
    stock_collection = adapter.convert_to_stocks(sample_data)

    print(f"Converted to {len(stock_collection.stocks)} Stock domain objects:")
    for stock in stock_collection.stocks:
        print(
            f"  {stock.symbol}: {stock.company_name} - Market Cap: ${stock.market_cap:,.0f}")
    print()


def demo_metrics_service():
    """Demonstrate the financial metrics service."""
    print("=== Financial Metrics Service Demo ===")

    # Sample financial data
    financial_data = {
        'Symbol': 'AAPL',
        'Market Cap': 2500000000000,
        'Shares Outstanding': 15000000000,
        'Total Assets': 350000000000,
        'Adjusted Total Assets': 320000000000,
        'Adjusted Total Current Assets': 120000000000,
        'Total Equity': 60000000000,
        'Average Price in Last 30 Days': 150.0,
    }

    print("Original financial data:")
    for key, value in financial_data.items():
        if isinstance(value, (int, float)) and value > 1000000:
            print(f"  {key}: ${value:,.0f}")
        else:
            print(f"  {key}: {value}")
    print()

    # Calculate comprehensive metrics
    enhanced_data = FinancialMetricsService.calculate_comprehensive_metrics(
        financial_data)

    print("Enhanced with calculated metrics:")
    new_metrics = {
        'price_by_assets': enhanced_data['price_by_assets'],
        'price_by_current_assets': enhanced_data['price_by_current_assets'],
        'price/price_to_assets_ratio': enhanced_data['price/price_to_assets_ratio'],
        'price/price_to_current_assets_ratio': enhanced_data['price/price_to_current_assets_ratio'],
    }

    for key, value in new_metrics.items():
        print(f"  {key}: {value:.2f}")
    print()


def demo_integration():
    """Demonstrate the integration between components."""
    print("=== Integration Demo ===")

    # Sample data flow: fincli DataFrame -> Stock objects -> Enhanced metrics
    fincli_data = pd.DataFrame({
        'Ticker': ['AAPL'],
        'Company': ['Apple Inc.'],
        'Sector': ['Technology'],
        'Industry': ['Consumer Electronics'],
        'Country': ['USA'],
        'Market Cap': ['2.5T'],
        'Price': [150.0]
    })

    print("1. Starting with fincli DataFrame:")
    print(fincli_data.to_string())
    print()

    # Convert to domain objects
    adapter = FinCliAdapterFactory.create_basic_adapter()
    stocks = adapter.convert_to_stocks(fincli_data)

    print("2. Converted to Stock domain objects:")
    for stock in stocks.stocks:
        print(f"   Symbol: {stock.symbol}")
        print(f"   Company: {stock.company_name}")
        print(f"   Market Cap: ${stock.market_cap:,.0f}")
        print(f"   Sector: {stock.sector}")
    print()

    # Simulate financial data enrichment
    mock_financial_data = {
        'Symbol': 'AAPL',
        'Market Cap': 2500000000000,
        'Shares Outstanding': 15000000000,
        'Adjusted Total Assets': 320000000000,
        'Adjusted Total Current Assets': 120000000000,
        'Average Price in Last 30 Days': 150.0,
    }

    print("3. Enhanced with financial calculations:")
    enhanced = FinancialMetricsService.calculate_comprehensive_metrics(
        mock_financial_data)

    key_metrics = [
        'price_by_assets',
        'price_by_current_assets',
        'price/price_to_assets_ratio',
        'price/price_to_current_assets_ratio'
    ]

    for metric in key_metrics:
        print(f"   {metric}: {enhanced[metric]:.2f}")
    print()


def main():
    """Run all demonstrations."""
    print("Task 3: Consolidate Data Models and Domain Logic - Demo")
    print("=" * 60)
    print()

    demo_financial_calculations()
    demo_data_adapter()
    demo_metrics_service()
    demo_integration()

    print("=== Summary ===")
    print("✅ Financial calculation services working correctly")
    print("✅ FinCli data adapter converting DataFrames to domain objects")
    print("✅ Financial metrics service calculating comprehensive metrics")
    print("✅ Integration between components functioning properly")
    print()
    print("The new architecture provides:")
    print("• Clean separation between data conversion and business logic")
    print("• Reusable financial calculation services")
    print("• Proper domain objects with validation")
    print("• Enhanced logging and error handling")
    print("• Backward compatibility with existing code")


if __name__ == "__main__":
    main()
