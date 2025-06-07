"""
Financial calculation service for domain-level financial computations.

This service contains business logic for financial calculations that operate
on financial data entities. It extracts calculation logic from the infrastructure
layer to provide a clean domain service.
"""
from typing import Optional
import pandas as pd

from shared.infrastructure.logging.log_manager import LogManager

logger = LogManager().get_logger("financial_calculation_service")


class FinancialCalculationService:
    """
    Service for performing financial calculations on financial data.

    This service implements the business logic for various financial calculations
    used throughout the application, ensuring consistency and reusability.
    """

    @staticmethod
    def calculate_price_to_data_ratio(asset_value: float, shares_outstanding: int) -> float:
        """
        Calculate price to data ratio.

        This calculates the per-share value of a specific asset or metric.

        Args:
            asset_value: The total asset value or financial metric
            shares_outstanding: Number of outstanding shares

        Returns:
            Price to data ratio, or 0 if invalid inputs

        Examples:
            >>> FinancialCalculationService.calculate_price_to_data_ratio(1000000, 100000)
            10.0
        """
        if shares_outstanding == 0 or asset_value == 0:
            return 0.0

        try:
            return float(asset_value) / float(shares_outstanding)
        except (ValueError, TypeError, ZeroDivisionError):
            logger.warn(
                f"Invalid inputs for price to data ratio: asset_value={asset_value}, shares={shares_outstanding}")
            return 0.0

    @staticmethod
    def calculate_ratio_between_values(value1: float, value2: float) -> float:
        """
        Calculate ratio between two values.

        Args:
            value1: First value (numerator)
            value2: Second value (denominator)

        Returns:
            Ratio of value1 to value2, or 0 if value2 is 0

        Examples:
            >>> FinancialCalculationService.calculate_ratio_between_values(100, 50)
            2.0
        """
        if value2 == 0:
            return 0.0

        try:
            return float(value1) / float(value2)
        except (ValueError, TypeError, ZeroDivisionError):
            logger.warn(
                f"Invalid inputs for ratio calculation: value1={value1}, value2={value2}")
            return 0.0

    @staticmethod
    def calculate_adjusted_assets(
        total_assets: float,
        goodwill: Optional[float] = None,
        other_non_current_assets: Optional[float] = None
    ) -> float:
        """
        Calculate adjusted total assets by removing goodwill and other non-current assets.

        This adjustment provides a more conservative view of a company's assets
        by removing intangible and potentially less liquid assets.

        Args:
            total_assets: Total assets value
            goodwill: Goodwill value to subtract (optional)
            other_non_current_assets: Other non-current assets to subtract (optional)

        Returns:
            Adjusted total assets value (always non-negative)

        Examples:
            >>> FinancialCalculationService.calculate_adjusted_assets(1000, 100, 50)
            850.0
        """
        if total_assets < 0:
            logger.warn(f"Negative total assets provided: {total_assets}")
            return 0.0

        adjusted = float(total_assets)

        # Subtract goodwill if available
        if goodwill is not None and goodwill > 0:
            adjusted -= float(goodwill)

        # Subtract other non-current assets if available
        if other_non_current_assets is not None and other_non_current_assets > 0:
            adjusted -= float(other_non_current_assets)

        # Ensure non-negative result
        return max(0.0, adjusted)

    @staticmethod
    def calculate_adjusted_current_assets(
        current_assets: float,
        inventory: Optional[float] = None,
        other_current_assets: Optional[float] = None,
        inventory_adjustment_factor: float = 0.3
    ) -> float:
        """
        Calculate adjusted current assets with inventory adjustment.

        This calculation applies a discount to inventory (default 30%) to account
        for potential obsolescence or liquidation challenges, and removes
        other current assets that may be less liquid.

        Args:
            current_assets: Current assets value
            inventory: Inventory value (optional)
            other_current_assets: Other current assets to subtract (optional)
            inventory_adjustment_factor: Factor to apply to inventory (default 0.3 for 30% discount)

        Returns:
            Adjusted current assets value (always non-negative)

        Examples:
            >>> FinancialCalculationService.calculate_adjusted_current_assets(1000, 200, 50)
            1010.0  # 1000 + (0.3 * 200) - 50
        """
        if current_assets < 0:
            logger.warn(f"Negative current assets provided: {current_assets}")
            return 0.0

        adjusted = float(current_assets)

        # Apply inventory adjustment if available (typically a discount)
        if inventory is not None and inventory > 0:
            inventory_adjustment = float(
                inventory) * float(inventory_adjustment_factor)
            adjusted += inventory_adjustment

        # Subtract other current assets if available
        if other_current_assets is not None and other_current_assets > 0:
            adjusted -= float(other_current_assets)

        # Ensure non-negative result
        return max(0.0, adjusted)

    @staticmethod
    def calculate_price_ratios(
        average_price: float,
        adjusted_total_assets: float,
        adjusted_current_assets: float,
        shares_outstanding: int
    ) -> tuple[float, float, float, float]:
        """
        Calculate comprehensive price ratios for a stock.

        This method calculates multiple price-based ratios that are commonly
        used in fundamental analysis.

        Args:
            average_price: Average stock price
            adjusted_total_assets: Adjusted total assets value
            adjusted_current_assets: Adjusted current assets value
            shares_outstanding: Number of outstanding shares

        Returns:
            Tuple of (price_by_assets, price_by_current_assets, 
                     price_to_assets_ratio, price_to_current_assets_ratio)

        Examples:
            >>> service = FinancialCalculationService()
            >>> service.calculate_price_ratios(50, 1000000, 500000, 100000)
            (10.0, 5.0, 5.0, 10.0)
        """
        # Calculate per-share asset values
        price_by_assets = FinancialCalculationService.calculate_price_to_data_ratio(
            adjusted_total_assets, shares_outstanding
        )

        price_by_current_assets = FinancialCalculationService.calculate_price_to_data_ratio(
            adjusted_current_assets, shares_outstanding
        )

        # Calculate price ratios
        price_to_assets_ratio = FinancialCalculationService.calculate_ratio_between_values(
            average_price, price_by_assets
        )

        price_to_current_assets_ratio = FinancialCalculationService.calculate_ratio_between_values(
            average_price, price_by_current_assets
        )

        return (
            price_by_assets,
            price_by_current_assets,
            price_to_assets_ratio,
            price_to_current_assets_ratio
        )


class AssetAdjustmentService:
    """
    Service for adjusting asset values based on business rules.

    This service handles the complex logic for adjusting asset values
    according to specific business rules and conservative valuation principles.
    """

    @staticmethod
    def adjust_balance_sheet_assets(
        balance_sheet_data: pd.Series,
        asset_type: str,
        adjustment_factor: float = 0.0,
        subtractions: Optional[list] = None
    ) -> Optional[float]:
        """
        Adjust asset values from balance sheet data using specific business rules.

        This method extracts and adjusts asset values from pandas Series data
        (typically from yfinance balance sheet data) according to specified rules.

        Args:
            balance_sheet_data: Pandas Series containing balance sheet data
            asset_type: The type of asset to extract (e.g., 'Total Assets')
            adjustment_factor: Factor to apply to inventory (if relevant)
            subtractions: List of asset types to subtract from the main asset

        Returns:
            Adjusted asset value or None if data is unavailable

        Note:
            This method is designed to work with the current yfinance data structure
            and may need adjustment if the data source changes.
        """
        if subtractions is None:
            subtractions = []

        try:
            # Get the main asset value (using iloc[1] for most recent quarter)
            if asset_type in balance_sheet_data.index:
                asset_value = balance_sheet_data.loc[asset_type].iloc[1]
            else:
                logger.warn(
                    f"Asset type '{asset_type}' not found in balance sheet data")
                return None
        except (KeyError, IndexError) as e:
            logger.error(f"Error accessing asset type '{asset_type}': {e}")
            return None

        # Apply subtractions
        for subtract_item in subtractions:
            try:
                if subtract_item in balance_sheet_data.index:
                    subtract_value = balance_sheet_data.loc[subtract_item].iloc[1]
                    if subtract_value is not None and subtract_value > 0:
                        asset_value -= subtract_value
            except (KeyError, IndexError) as e:
                logger.warn(f"Could not subtract '{subtract_item}': {e}")
                continue

        # Apply inventory adjustment if relevant
        if adjustment_factor != 0:
            try:
                if 'Inventory' in balance_sheet_data.index:
                    inventory = balance_sheet_data.loc['Inventory'].iloc[1]
                    if inventory is not None and inventory > 0:
                        asset_value += (adjustment_factor * inventory)
            except (KeyError, IndexError) as e:
                logger.warn(f"Could not apply inventory adjustment: {e}")

        return float(asset_value) if asset_value is not None else None


class FinancialMetricsService:
    """
    Service for calculating advanced financial metrics and indicators.

    This service provides higher-level financial metrics that combine
    multiple data points to provide business insights.
    """

    @staticmethod
    def calculate_comprehensive_metrics(financial_data: dict) -> dict:
        """
        Calculate comprehensive financial metrics from raw financial data.

        This method takes raw financial data and calculates derived metrics
        that are commonly used in fundamental analysis.

        Args:
            financial_data: Dictionary containing raw financial data

        Returns:
            Dictionary with calculated metrics added

        Example:
            >>> data = {
            ...     'Symbol': 'AAPL',
            ...     'Market Cap': 2000000000,
            ...     'Shares Outstanding': 100000000,
            ...     'Total Assets': 1000000000,
            ...     'Adjusted Total Assets': 900000000,
            ...     'Adjusted Total Current Assets': 500000000,
            ...     'Average Price in Last 30 Days': 150.0
            ... }
            >>> FinancialMetricsService.calculate_comprehensive_metrics(data)
            {...}  # Returns data with additional calculated metrics
        """
        enhanced_data = financial_data.copy()

        # Extract required values
        average_price = financial_data.get('Average Price in Last 30 Days', 0)
        adjusted_total_assets = financial_data.get('Adjusted Total Assets', 0)
        adjusted_current_assets = financial_data.get(
            'Adjusted Total Current Assets', 0)
        shares_outstanding = financial_data.get('Shares Outstanding', 0)

        # Calculate price ratios
        (
            price_by_assets,
            price_by_current_assets,
            price_to_assets_ratio,
            price_to_current_assets_ratio
        ) = FinancialCalculationService.calculate_price_ratios(
            average_price,
            adjusted_total_assets,
            adjusted_current_assets,
            shares_outstanding
        )

        # Add calculated metrics to the data
        enhanced_data.update({
            'price_by_assets': price_by_assets,
            'price_by_current_assets': price_by_current_assets,
            'price/price_to_assets_ratio': price_to_assets_ratio,
            'price/price_to_current_assets_ratio': price_to_current_assets_ratio,
        })

        logger.debug(f"Calculated comprehensive metrics for {financial_data.get('Symbol', 'Unknown')}", context={
            "symbol": financial_data.get('Symbol'),
            "calculated_metrics": {
                "price_by_assets": price_by_assets,
                "price_by_current_assets": price_by_current_assets,
                "price_to_assets_ratio": price_to_assets_ratio,
                "price_to_current_assets_ratio": price_to_current_assets_ratio,
            }
        })

        return enhanced_data
