"""
Simplified adapter for converting FinCli DataFrame data to domain objects.

This module provides basic functionality to convert raw DataFrame data from the fincli
stock screener into properly structured domain objects.
"""
import pandas as pd
from pandas import DataFrame, Series
from typing import List, Optional, Callable, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from fundainsight.domain.models.stock import Stock, StockCollection
from fundainsight.domain.models.financial_data import FinancialData
from shared.infrastructure.logging.log_manager import LogManager

logger = LogManager().get_logger("fincli_adapter")


class FinCliDataAdapter:
    """
    Simplified adapter to convert FinCli DataFrame data to domain objects.
    """

    def __init__(self, financial_data_provider: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None):
        """
        Initialize the adapter.

        Args:
            financial_data_provider: Optional function to get financial data for a ticker
        """
        self.financial_data_provider = financial_data_provider

    def convert_to_stocks(self, df: DataFrame) -> StockCollection:
        """
        Convert a DataFrame from fincli to a collection of Stock domain objects.

        Args:
            df: DataFrame from fincli containing stock screening results

        Returns:
            StockCollection containing Stock domain objects
        """
        if df is None or df.empty:
            logger.warn("Empty DataFrame provided to convert_to_stocks")
            return StockCollection(stocks=[])

        logger.info(f"Converting {len(df)} rows to Stock domain objects")

        stocks = []
        for _, row in df.iterrows():
            try:
                stock = self._convert_row_to_stock(row)
                stocks.append(stock)
            except Exception as e:
                logger.error(f"Failed to convert row to Stock: {e}")
                continue

        logger.info(f"Successfully converted {len(stocks)} stocks")
        return StockCollection(stocks=stocks)

    def convert_to_financial_data(self, df: DataFrame, use_parallel: bool = False) -> List[FinancialData]:
        """
        Convert a DataFrame from fincli to FinancialData domain objects.

        Args:
            df: DataFrame from fincli containing stock screening results
            use_parallel: Whether to use parallel processing for financial data retrieval

        Returns:
            List of FinancialData domain objects
        """
        if df is None or df.empty:
            logger.warn("Empty DataFrame provided to convert_to_financial_data")
            return []

        if self.financial_data_provider is None:
            raise ValueError("financial_data_provider must be set to convert to FinancialData")

        logger.info(f"Converting {len(df)} rows to FinancialData objects")

        # Extract tickers for financial data retrieval
        tickers = df['Symbol'].tolist() if 'Symbol' in df.columns else df['Ticker'].tolist()

        # Get detailed financial data
        if use_parallel:
            with ThreadPoolExecutor() as executor:
                financial_results = list(executor.map(
                    self.financial_data_provider, tickers))
        else:
            financial_results = [self.financial_data_provider(
                ticker) for ticker in tickers]

        # Filter out None results and merge with original data
        valid_results = [
            result for result in financial_results if result is not None]
        financial_df = pd.DataFrame(valid_results)

        if financial_df.empty:
            return []

        # Merge with original DataFrame to get additional info like Sector, Industry, Country
        merged_data = self._merge_dataframes(df, financial_df)

        # Convert to FinancialData objects
        financial_data_objects = []
        for _, row in merged_data.iterrows():
            try:
                financial_data = FinancialData.from_dict(row.to_dict())
                financial_data_objects.append(financial_data)
            except Exception as e:
                logger.error(f"Failed to create FinancialData from row: {e}")
                continue

        logger.info(f"Successfully created {len(financial_data_objects)} FinancialData objects")
        
        return financial_data_objects

    def _convert_row_to_stock(self, row: Series) -> Stock:
        """
        Convert a single DataFrame row to a Stock domain object.

        Args:
            row: Single row from fincli DataFrame

        Returns:
            Stock domain object
        """
        # Handle market cap conversion if it's a string
        market_cap = self._parse_market_cap(row.get('Market Cap'))

        return Stock(
            symbol=str(row.get('Ticker', row.get('Symbol', ''))).strip(),
            company_name=str(row.get('Company', '')).strip(),
            sector=str(row.get('Sector', '')).strip() if pd.notna(
                row.get('Sector')) else None,
            industry=str(row.get('Industry', '')).strip(
            ) if pd.notna(row.get('Industry')) else None,
            country=str(row.get('Country', '')).strip(
            ) if pd.notna(row.get('Country')) else None,
            market_cap=market_cap,
            price=float(row.get('Price', 0)) if pd.notna(
                row.get('Price')) and row.get('Price') != '-' else None
        )

    def _parse_market_cap(self, market_cap_value) -> Optional[float]:
        """
        Parse market cap value from string format to float.

        Args:
            market_cap_value: Market cap value (could be string like "1.2B" or numeric)

        Returns:
            Market cap as float or None if invalid
        """
        if market_cap_value is None or pd.isna(market_cap_value):
            return None

        # If already numeric, return as is
        if isinstance(market_cap_value, (int, float)):
            return float(market_cap_value)

        # Handle string format (e.g., "1.2B", "500M", etc.)
        if isinstance(market_cap_value, str):
            market_cap_str = market_cap_value.strip().replace(',', '')

            if market_cap_str in ['-', 'N/A', '']:
                return None

            # Handle suffixes
            try:
                if market_cap_str.endswith('B'):
                    return float(market_cap_str[:-1]) * 1_000_000_000
                elif market_cap_str.endswith('M'):
                    return float(market_cap_str[:-1]) * 1_000_000
                elif market_cap_str.endswith('T'):
                    return float(market_cap_str[:-1]) * 1_000_000_000_000
                else:
                    return float(market_cap_str)
            except (ValueError, TypeError):
                logger.warn(
                    f"Could not parse market cap value: {market_cap_value}")
                return None

        return None

    def _merge_dataframes(self, original_df: DataFrame, financial_df: DataFrame) -> DataFrame:
        """
        Merge original DataFrame with financial data DataFrame.

        This function replicates the logic from the old assign_old_df_to_new_df function,
        which assigns columns by position rather than using complex DataFrame merging.

        Args:
            original_df: Original DataFrame from fincli
            financial_df: DataFrame with detailed financial data

        Returns:
            Financial DataFrame with additional columns assigned from original_df
        """
        logger.info(f"Merging DataFrames: original={len(original_df)}, financial={len(financial_df)}")

        # Make a copy to avoid modifying the original financial_df
        result_df = financial_df.copy()

        # Columns to assign from original DataFrame (matching old code)
        columns_to_assign = ['Ticker', 'Sector', 'Industry', 'Country']

        for column in columns_to_assign:
            if column in original_df.columns:
                self._assign_column_by_position(original_df, result_df, column)
            else:
                logger.warn(f"Column '{column}' not found in original DataFrame")

        logger.info(f"Successfully merged DataFrames, result has {len(result_df)} rows")
        
        return result_df

    def _assign_column_by_position(self, source_df: DataFrame, target_df: DataFrame, column: str) -> None:
        """
        Assign a column from source DataFrame to target DataFrame by position.

        This replicates the exact logic from assign_old_df_to_new_df function.

        Args:
            source_df: DataFrame to copy column from
            target_df: DataFrame to assign column to (modified in place)
            column: Name of the column to assign
        """
        if len(target_df) == len(source_df[column]):
            # Same length - direct assignment
            target_df[column] = source_df[column].values
            logger.debug(
                f"Assigned column '{column}' - lengths match ({len(target_df)})")
        else:
            # Different lengths - assign up to minimum length, fill rest with NaN
            min_length = min(len(target_df), len(source_df[column]))

            # Initialize the column with NaN first
            target_df[column] = np.nan

            # Assign values up to min_length using .loc to avoid the warning
            if min_length > 0:
                target_df.loc[:min_length-1,
                              column] = source_df[column].values[:min_length]

            logger.warn(
                f"Column '{column}' length mismatch: target={len(target_df)}, source={len(source_df[column])}, assigned={min_length}")


class FinCliAdapterFactory:
    """
    Factory for creating FinCliDataAdapter instances.
    """

    @staticmethod
    def create_with_yfinance_provider() -> FinCliDataAdapter:
        """
        Create adapter with yfinance provider for financial data.

        Returns:
            FinCliDataAdapter configured with yfinance provider
        """
        from shared.domain.services.financial_data_provider import get_financial_data
        return FinCliDataAdapter(financial_data_provider=get_financial_data)

    @staticmethod
    def create_basic_adapter() -> FinCliDataAdapter:
        """
        Create adapter without financial data provider (basic stock info only).

        Returns:
            FinCliDataAdapter for basic stock conversion only
        """
        return FinCliDataAdapter(financial_data_provider=None)
