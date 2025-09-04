"""
Enhanced stock picker module with backward compatibility.

This module provides a comprehensive implementation of the stock picking logic
that combines the new domain-driven design architecture with backward compatibility
for the original implementation.
"""
import numpy as np
import pandas as pd
from pandas import DataFrame
import cProfile
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any

from shared.infrastructure.config import get_config
from shared.infrastructure.config.api_keys_config import get_api_keys_config
from shared.domain.adapters.fincli_data_adapter import FinCliAdapterFactory, FinCliDataAdapter
from shared.domain.services.financial_calculation_service import FinancialMetricsService
from shared.domain.services.financial_data_provider import FinancialDataProviderFactory
from fundainsight.domain.models.financial_data import FinancialData
from fundainsight.calculators.filters import Filters
from fundainsight.calculators.equity_calc import get_financial_data, calculate_price_to_data, ratio_between_two_values
from shared.infrastructure.logging.log_manager import LogManager

logger = LogManager().get_logger("stock_picker")


# Backward compatibility functions
def add_new_columns(df: DataFrame) -> DataFrame:
    """
    Add calculated columns to the DataFrame.

    This function maintains the exact logic from the original picker.py
    to ensure backward compatibility.

    Args:
        df: DataFrame with financial data

    Returns:
        DataFrame with additional calculated columns
    """
    df["price_by_assets"] = df.apply(
        lambda x: calculate_price_to_data(x, 'Adjusted Total Assets'), axis=1)
    df["price_by_current_assets"] = df.apply(
        lambda x: calculate_price_to_data(x, 'Adjusted Total Current Assets'), axis=1)
    df["price/price_to_current_assets_ratio"] = df.apply(lambda x: ratio_between_two_values(
        x["Average Price in Last 30 Days"], x["price_by_current_assets"]), axis=1)
    df["price/price_to_assets_ratio"] = df.apply(lambda x: ratio_between_two_values(
        x["Average Price in Last 30 Days"], x["price_by_assets"]), axis=1)
    return df


def assign_old_df_to_new_df(old_df: DataFrame, new_df: DataFrame, colum: str) -> DataFrame:
    """
    Assign columns from old DataFrame to new DataFrame by position.

    This function maintains the exact logic from the original picker.py
    to ensure backward compatibility.

    Args:
        old_df: Source DataFrame
        new_df: Target DataFrame (modified in place)
        colum: Column name to assign

    Returns:
        Modified new_df
    """
    if len(new_df) == len(old_df[colum]):
        new_df[colum] = old_df[colum].values
    else:
        min_length = min(len(new_df), len(old_df[colum]))
        new_df[colum] = old_df[colum].values[:min_length]
        # Optionally, fill the remaining values with NaN or another placeholder
        if len(new_df) > min_length:
            new_df[colum][min_length:] = np.nan
    return new_df


def picker_original(df: Optional[DataFrame]) -> Optional[DataFrame]:
    """
    Original picker implementation for backward compatibility.

    This function maintains the exact logic from the original picker.py
    to ensure existing code continues to work without changes.

    Args:
        df: DataFrame containing stock symbols

    Returns:
        DataFrame with filtered financial data
    """
    if df is None:
        return None

    logger.info("Getting Financial Data --->")

    with ThreadPoolExecutor() as executor:
        results = list(executor.map(get_financial_data, df["Symbol"]))

        valid_results = [res for res in results if res is not None]
        df_fundamentals = DataFrame(valid_results)

    # Original column assignment logic
    assign_old_df_to_new_df(df, df_fundamentals, "Ticker")
    assign_old_df_to_new_df(df, df_fundamentals, "Sector")
    assign_old_df_to_new_df(df, df_fundamentals, "Industry")
    assign_old_df_to_new_df(df, df_fundamentals, "Country")

    logger.info("Calculating the price to assets ratio --->")

    df_fundamentals = add_new_columns(df_fundamentals)

    # Filter columns
    columns_to_retain = [
        'Ticker',
        'Sector',
        'Industry',
        'Country',
        'Market Cap',
        'Average Price in Last 30 Days',
        'price_by_assets',
        'price_by_current_assets',
        'price/price_to_current_assets_ratio',
        'price/price_to_assets_ratio'
    ]

    df_fundamentals = df_fundamentals[columns_to_retain]

    file_path = get_config().file_path("funda_insight_result_unfiltered")
    df_fundamentals.to_csv(file_path, index=False)

    df_fundamentals = Filters(df_fundamentals).filter_countries(["Brazil", "Chile", "India", "Bermuda", "China"]).filter_sector(
        "Energy").filter_price("price/price_to_current_assets_ratio", 1).filter_invalid_data(columns=["Market Cap", "Total Assets", "Total Equity", "Adjusted Total Assets", "Adjusted Total Current Assets"], threshold=0).get_data()

    return df_fundamentals


class StockPicker:
    """
    Enhanced stock picker using domain services and adapters with composite provider support.

    This class provides an improved implementation of the stock picking logic
    with better separation of concerns and use of domain-driven design patterns.
    Now supports multiple data providers with automatic fallback.
    """

    def __init__(self, use_composite_provider: bool = True):
        """
        Initialize the enhanced stock picker with dependencies.

        Args:
            use_composite_provider: Whether to use composite provider with fallbacks (default: True)
        """
        # Get API keys configuration
        api_config = get_api_keys_config()

        # Create provider based on configuration
        if use_composite_provider and api_config.enable_fallback_providers:
            # Use composite provider with multiple sources
            self.provider = FinancialDataProviderFactory.create_composite_provider(
                api_config)
            logger.info(
                f"Using composite provider with: {api_config.get_enabled_providers()}")
        else:
            # Use single yfinance provider
            self.provider = FinancialDataProviderFactory.create_yfinance_provider()
            logger.info("Using single yfinance provider")

        # Create adapter with the configured provider
        # Create a callable that uses our configured provider
        def provider_callable(symbol: str) -> Optional[Dict[str, Any]]:
            return self.provider.get_financial_data(symbol)

        self.adapter = FinCliDataAdapter(
            financial_data_provider=provider_callable)
        self.metrics_service = FinancialMetricsService()
        self.api_config = api_config

    def pick_stocks(self, df: Optional[DataFrame]) -> Optional[DataFrame]:
        """
        Pick stocks using enhanced domain-driven approach.

        Args:
            df: DataFrame containing stock screening results from fincli

        Returns:
            DataFrame with enhanced financial data and filtering applied
        """
        if df is None:
            logger.warn("No DataFrame provided to pick_stocks")
            return None

        logger.info(f"Starting stock picking process for {len(df)} stocks")

        try:
            # Step 1: Convert to domain objects with financial data enrichment
            financial_data_objects = self.adapter.convert_to_financial_data(
                df, use_parallel=True)

            if not financial_data_objects:
                logger.warn(
                    "No financial data objects created from input DataFrame")
                return None

            logger.info(
                f"Successfully created {len(financial_data_objects)} financial data objects")

            # Step 2: Convert back to DataFrame with enhanced metrics
            enhanced_df = self._convert_to_enhanced_dataframe(
                financial_data_objects)

            # Step 3: Add calculated metrics using domain services
            enhanced_df = self._add_calculated_metrics(enhanced_df)

            # Step 4: Save unfiltered results
            self._save_unfiltered_results(enhanced_df)

            # Step 5: Apply business filters
            filtered_df = self._apply_business_filters(enhanced_df)

            logger.info(
                f"Enhanced stock picking completed. Filtered results: {len(filtered_df) if filtered_df is not None else 0}")

            return filtered_df

        except Exception as e:
            logger.error(f"Error during enhanced stock picking: {e}")
            return None

        finally:
            # Log provider performance statistics if available
            self._log_provider_statistics()

    def _log_provider_statistics(self):
        """Log performance statistics from the data provider if available."""
        try:
            # Check if it's a composite provider
            if hasattr(self.provider, 'get_provider_stats') and callable(getattr(self.provider, 'get_provider_stats')):
                stats = getattr(self.provider, 'get_provider_stats')()
                logger.info("📊 Provider Performance Statistics:")
                for provider_name, provider_stats in stats.items():
                    success_rate = float(provider_stats.get(
                        'success_rate', '0%').replace('%', ''))
                    logger.info(f"  • {provider_name}: {success_rate:.1f}% success rate "
                                f"({provider_stats.get('successes', 0)}/{provider_stats.get('total_requests', 0)} requests)")
            # Check if it's a single provider with statistics
            elif hasattr(self.provider, 'get_statistics') and callable(getattr(self.provider, 'get_statistics')):
                stats = getattr(self.provider, 'get_statistics')()
                logger.info("📊 Provider Performance Statistics:")
                success_rate = stats.get('success_rate', 0)
                logger.info(f"  • Single provider: {success_rate:.1f}% success rate "
                            f"({stats.get('successful_requests', 0)}/{stats.get('total_requests', 0)} requests)")

                avg_response_time = stats.get('average_response_time', 0)
                if avg_response_time > 0:
                    logger.info(
                        f"    Average response time: {avg_response_time:.2f}s")

            # Log enabled providers info
            logger.info(
                f"🔧 Configuration: Primary provider = {self.api_config.primary_provider}")
            logger.info(
                f"🔧 Enabled providers: {', '.join(self.api_config.get_enabled_providers())}")

        except Exception as e:
            logger.debug(f"Could not retrieve provider statistics: {e}")

    def _convert_to_enhanced_dataframe(self, financial_data_objects: List[FinancialData]) -> DataFrame:
        """
        Convert FinancialData objects to enhanced DataFrame.

        Args:
            financial_data_objects: List of FinancialData domain objects

        Returns:
            Enhanced DataFrame with comprehensive financial data
        """
        logger.info("Converting financial data objects to enhanced DataFrame")

        # Convert domain objects to dictionaries
        data_dicts = []
        for financial_data in financial_data_objects:
            try:
                data_dict = financial_data.to_dict()
                # Calculate additional metrics using domain service
                enhanced_dict = self.metrics_service.calculate_comprehensive_metrics(
                    data_dict)
                data_dicts.append(enhanced_dict)
            except Exception as e:
                logger.error(
                    f"Error converting financial data for {financial_data.symbol}: {e}")
                continue

        if not data_dicts:
            logger.warn("No valid data dictionaries created")
            return DataFrame()

        enhanced_df = DataFrame(data_dicts)
        logger.info(
            f"Created enhanced DataFrame with {len(enhanced_df)} rows and {len(enhanced_df.columns)} columns")

        return enhanced_df

    def _add_calculated_metrics(self, df: DataFrame) -> DataFrame:
        """
        Add calculated metrics to the DataFrame using domain services.

        Args:
            df: DataFrame with financial data

        Returns:
            DataFrame with additional calculated metrics
        """
        logger.info("Adding calculated metrics using domain services")

        # Add legacy columns for backward compatibility
        try:
            df = add_new_columns(df)
        except Exception as e:
            logger.error(f"Error adding legacy calculated columns: {e}")

        return df

    def _save_unfiltered_results(self, df: DataFrame) -> None:
        """
        Save unfiltered results to CSV file.

        Args:
            df: DataFrame to save
        """
        try:
            file_path = get_config().file_path("funda_insight_result_unfiltered")

            # Select columns to retain for output
            columns_to_retain = [
                'Ticker',
                'Sector',
                'Industry',
                'Country',
                'Market Cap',
                'Average Price in Last 30 Days',
                'price_by_assets',
                'price_by_current_assets',
                'price/price_to_current_assets_ratio',
                'price/price_to_assets_ratio'
            ]

            # Only keep columns that exist in the DataFrame
            available_columns = [
                col for col in columns_to_retain if col in df.columns]
            output_df = df[available_columns]

            output_df.to_csv(file_path, index=False)
            logger.info(f"Saved unfiltered results to {file_path}", context={
                "file_path": file_path,
                "row_count": len(output_df),
                "column_count": len(available_columns)
            })

        except Exception as e:
            logger.error(f"Error saving unfiltered results: {e}")

    def _apply_business_filters(self, df: DataFrame) -> Optional[DataFrame]:
        """
        Apply business logic filters to the enhanced data.

        Args:
            df: Enhanced DataFrame with calculated metrics

        Returns:
            Filtered DataFrame or None if no data passes filters
        """
        logger.info("Applying business filters")

        try:
            # Ensure required columns exist
            required_columns = [
                'Ticker', 'Sector', 'Industry', 'Country', 'Market Cap',
                'Average Price in Last 30 Days', 'price_by_assets', 'price_by_current_assets',
                'price/price_to_current_assets_ratio', 'price/price_to_assets_ratio'
            ]

            missing_columns = [
                col for col in required_columns if col not in df.columns]
            if missing_columns:
                logger.error(
                    f"Missing required columns for filtering: {missing_columns}")
                return None

            # Apply filters using the existing Filters class
            filters = Filters(df)

            # Apply business logic filters
            filtered_df = (filters
                           .filter_countries(["Brazil", "Chile", "India", "Bermuda", "China"])
                           .filter_sector("Energy")
                           .filter_price("price/price_to_current_assets_ratio", 1)
                           .filter_invalid_data(columns=["Market Cap", "Total Assets", "Total Equity", "Adjusted Total Assets", "Adjusted Total Current Assets"], threshold=0)
                           .get_data())

            logger.info(f"Applied business filters, resulting in {len(filtered_df)} stocks", context={
                "original_count": len(df),
                "filtered_count": len(filtered_df)
            })

            return filtered_df

        except Exception as e:
            logger.error(f"Error applying business filters: {e}")
            return None


def picker_enhanced(df: Optional[DataFrame], use_new_architecture: bool = True) -> Optional[DataFrame]:
    """
    Enhanced picker implementation using new domain-driven architecture.

    This function provides improved functionality while maintaining
    backward compatibility through the use_new_architecture flag.

    Args:
        df: DataFrame containing stock symbols
        use_new_architecture: Whether to use the new domain-driven architecture

    Returns:
        DataFrame with filtered financial data
    """
    if df is None:
        return None

    if not use_new_architecture:
        # Fall back to original implementation
        return picker_original(df)

    logger.info(
        f"Using enhanced picker with new architecture for {len(df)} stocks")

    try:
        # Use the StockPicker class for enhanced implementation
        stock_picker = StockPicker()
        return stock_picker.pick_stocks(df)

    except Exception as e:
        logger.error(
            f"Error in enhanced picker: {e}, falling back to original implementation")
        return picker_original(df)


def picker(df: Optional[DataFrame], use_enhanced: bool = True) -> Optional[DataFrame]:
    """
    Main picker function with automatic architecture selection.

    This function provides the primary interface for stock picking with
    options for enhanced or original implementation.

    Args:
        df: DataFrame containing stock screening results from fincli
        use_enhanced: Whether to use the enhanced implementation (default: True)

    Returns:
        DataFrame with enhanced financial data and filtering applied
    """
    if use_enhanced:
        try:
            return picker_enhanced(df, use_new_architecture=True)
        except Exception as e:
            logger.error(
                f"Enhanced picker failed: {e}, falling back to original")
            return picker_original(df)
    else:
        return picker_original(df)


if __name__ == "__main__":
    # Sample DataFrame for testing
    df_sample = DataFrame({
        "Symbol": ["AAPL", "MSFT", "GOOGL"],
        "Ticker": ["AAPL", "MSFT", "GOOGL"]
    })

    profiler = cProfile.Profile()
    profiler.enable()

    # Test both implementations
    print("Testing original implementation...")
    result_original = picker_original(df_sample)

    print("Testing enhanced implementation...")
    result_enhanced = picker_enhanced(df_sample, use_new_architecture=True)

    profiler.disable()
    profiler.dump_stats("profile_results.pstat")

    print(
        f"Original result shape: {result_original.shape if result_original is not None else 'None'}")
    print(
        f"Enhanced result shape: {result_enhanced.shape if result_enhanced is not None else 'None'}")
