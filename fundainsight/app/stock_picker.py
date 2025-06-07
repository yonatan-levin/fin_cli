"""
Enhanced picker module using domain-driven design patterns.

This module provides an improved implementation of the stock picking logic
using shared domain services, adapters, and proper separation of concerns.
"""
import pandas as pd
from pandas import DataFrame
from typing import List, Optional

from shared.infrastructure.config import get_config
from shared.domain.adapters.fincli_data_adapter import FinCliAdapterFactory
from shared.domain.services.financial_calculation_service import FinancialMetricsService
from fundainsight.domain.models.financial_data import FinancialData
from fundainsight.calculators.filters import Filters
from shared.infrastructure.logging.log_manager import LogManager

logger = LogManager().get_logger("picker_enhanced")


class StockPicker:
    """
    Enhanced stock picker using domain services and adapters.

    This class provides an improved implementation of the stock picking logic
    with better separation of concerns and use of domain-driven design patterns.
    """

    def __init__(self):
        """Initialize the enhanced stock picker with dependencies."""
        self.adapter = FinCliAdapterFactory.create_with_yfinance_provider()
        self.metrics_service = FinancialMetricsService()

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
            financial_data_objects = self.adapter.convert_to_financial_data(df, use_parallel=True)

            if not financial_data_objects:
                logger.warn("No financial data objects created from input DataFrame")
                return None

            logger.info(f"Successfully created {len(financial_data_objects)} financial data objects")

            # Step 2: Convert back to DataFrame with enhanced metrics
            enhanced_df = self._convert_to_enhanced_dataframe(financial_data_objects)

            # Step 3: Add calculated metrics using domain services
            enhanced_df = self._add_calculated_metrics(enhanced_df)

            # Step 4: Save unfiltered results
            self._save_unfiltered_results(enhanced_df)

            # Step 5: Apply business filters
            filtered_df = self._apply_business_filters(enhanced_df)

            logger.info(f"Enhanced stock picking completed. Filtered results: {len(filtered_df) if filtered_df is not None else 0}")

            return filtered_df

        except Exception as e:
            logger.error(f"Error during enhanced stock picking: {e}")
            return None

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

        # The metrics are already calculated in _convert_to_enhanced_dataframe
        # This method can be used for additional calculations if needed

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

def picker(df: Optional[DataFrame]) -> Optional[DataFrame]:
    """
    Enhanced picker function using the new domain-driven architecture.

    This function provides backward compatibility with the existing picker
    while leveraging the new domain services and adapters.

    Args:
        df: DataFrame containing stock screening results from fincli

    Returns:
        DataFrame with enhanced financial data and filtering applied
    """
    picker = StockPicker()
    return picker.pick_stocks(df)
