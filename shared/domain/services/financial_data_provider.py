"""
Financial data provider service - A facade for yfinance integration.

This service provides a clean interface for retrieving financial data using yfinance
while leveraging yfinance's native capabilities like caching, retry logic, and session management.
"""
from typing import Optional, Dict, Any, List
import yfinance as yf
from pandas import DataFrame
import pandas as pd

from shared.infrastructure.logging.log_manager import LogManager
from .financial_calculation_service import FinancialCalculationService

logger = LogManager().get_logger("financial_data_provider")


class YFinanceDataProvider:
    """
    A facade for yfinance that provides a clean interface for financial data retrieval.

    This provider leverages yfinance's native capabilities including:
    - Built-in caching and session management
    - Native retry logic and rate limiting
    - Comprehensive data access through simple APIs
    """

    def __init__(self, session=None):
        """
        Initialize the provider.

        Args:
            session: Optional requests session to use with yfinance
        """
        self._session = session

    def get_financial_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive financial data for a ticker using yfinance.

        This method leverages yfinance's native capabilities to retrieve
        financial data, balance sheet information, and market data.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary containing financial data or None if failed
        """
        logger.info(f"Retrieving financial data for {ticker}")

        try:
            # Create yfinance Ticker object (yfinance handles caching and sessions)
            yf_ticker = yf.Ticker(ticker, session=self._session)

            # Get basic info (yfinance handles retries and rate limiting)
            ticker_info = yf_ticker.info
            if not ticker_info:
                logger.warning(f"No ticker info available for {ticker}")
                return None

            # Get quarterly balance sheet (most recent data)
            balance_sheet = yf_ticker.quarterly_balance_sheet
            if balance_sheet is None or balance_sheet.empty:
                logger.warning(f"No balance sheet data available for {ticker}")
                return None

            # Extract essential market data
            shares_outstanding = ticker_info.get('sharesOutstanding')
            market_cap = ticker_info.get('marketCap')

            if not shares_outstanding or not market_cap:
                logger.warning(f"Missing essential market data for {ticker}")
                return None

            # Extract balance sheet data (most recent quarter - index 0 in yfinance)
            try:
                total_assets = self._get_balance_sheet_value(
                    balance_sheet, 'Total Assets')
                total_equity = self._get_balance_sheet_value(
                    balance_sheet, 'Stockholders Equity')
                current_assets = self._get_balance_sheet_value(
                    balance_sheet, 'Current Assets')

                # Optional items for adjustments
                goodwill = self._get_balance_sheet_value(
                    balance_sheet, 'Goodwill', default=0)
                other_non_current = self._get_balance_sheet_value(
                    balance_sheet, 'Other Non Current Assets', default=0)
                inventory = self._get_balance_sheet_value(
                    balance_sheet, 'Inventory', default=0)
                other_current = self._get_balance_sheet_value(
                    balance_sheet, 'Other Current Assets', default=0)

            except Exception as e:
                logger.error(
                    f"Error extracting balance sheet data for {ticker}: {e}")
                return None

            # Get historical price data using yfinance's native history method
            try:
                # yfinance handles caching for historical data
                history_30d = yf_ticker.history(period="1mo")
                if history_30d.empty:
                    average_price_30d = ticker_info.get('currentPrice', 0)
                    logger.info(
                        f"Using current price for {ticker} (no history available)")
                else:
                    average_price_30d = float(history_30d['Close'].median())
            except Exception as e:
                logger.warning(
                    f"Could not get price history for {ticker}: {e}")
                average_price_30d = ticker_info.get('currentPrice', 0)

            # Calculate adjusted assets using domain service
            adjusted_total_assets = FinancialCalculationService.calculate_adjusted_assets(
                total_assets, goodwill, other_non_current
            )

            adjusted_current_assets = FinancialCalculationService.calculate_adjusted_current_assets(
                current_assets, inventory, other_current, inventory_adjustment_factor=0.3
            )

            # Prepare comprehensive result
            result = {
                'Ticker': ticker,
                'Market Cap': market_cap,
                'Shares Outstanding': shares_outstanding,
                'Total Assets': total_assets,
                'Adjusted Total Assets': adjusted_total_assets,
                'Current Assets': current_assets,
                'Adjusted Total Current Assets': adjusted_current_assets,
                'Total Equity': total_equity,
                'Average Price in Last 30 Days': average_price_30d,
                'Goodwill': goodwill,
                'Inventory': inventory,
                'Other Current Assets': other_current,
                'Other Non Current Assets': other_non_current,
            }

            logger.info(f"Successfully retrieved financial data for {ticker}")
            return result

        except Exception as e:
            logger.error(
                f"Failed to retrieve financial data for {ticker}: {e}")
            return None

    def get_multiple_financial_data(self, tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get financial data for multiple tickers efficiently.

        Uses yfinance's Tickers class for efficient batch processing.

        Args:
            tickers: List of ticker symbols

        Returns:
            Dictionary mapping ticker symbols to their financial data
        """
        logger.info(f"Retrieving financial data for {len(tickers)} tickers")

        try:
            # Use yfinance's native multi-ticker support
            tickers_obj = yf.Tickers(' '.join(tickers), session=self._session)

            results = {}
            for ticker in tickers:
                try:
                    # Access individual ticker from the Tickers object
                    ticker_obj = tickers_obj.tickers[ticker]

                    # Use the same logic as single ticker but with the ticker object
                    result = self._extract_financial_data_from_ticker(
                        ticker, ticker_obj)
                    results[ticker] = result

                except Exception as e:
                    logger.error(f"Error processing {ticker}: {e}")
                    results[ticker] = None

            success_count = sum(1 for v in results.values() if v is not None)
            logger.info(
                f"Successfully retrieved data for {success_count}/{len(tickers)} tickers")

            return results

        except Exception as e:
            logger.error(f"Failed to retrieve multiple financial data: {e}")
            return {ticker: None for ticker in tickers}

    def get_market_data(self, ticker: str, period: str = "1mo") -> Optional[DataFrame]:
        """
        Get historical market data for a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Period for historical data (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)

        Returns:
            DataFrame with historical market data or None if failed
        """
        try:
            yf_ticker = yf.Ticker(ticker, session=self._session)
            history = yf_ticker.history(period=period)

            if history.empty:
                logger.warning(f"No market data available for {ticker}")
                return None

            logger.info(
                f"Retrieved {len(history)} days of market data for {ticker}")
            return history

        except Exception as e:
            logger.error(f"Failed to retrieve market data for {ticker}: {e}")
            return None

    def get_company_info(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get basic company information for a ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with company information or None if failed
        """
        try:
            yf_ticker = yf.Ticker(ticker, session=self._session)
            info = yf_ticker.info

            if not info:
                logger.warning(f"No company info available for {ticker}")
                return None

            logger.info(f"Retrieved company info for {ticker}")
            return info

        except Exception as e:
            logger.error(f"Failed to retrieve company info for {ticker}: {e}")
            return None

    def _get_balance_sheet_value(self, balance_sheet: DataFrame, item: str, default=None) -> float:
        """
        Safely extract a value from balance sheet data.

        Args:
            balance_sheet: Balance sheet DataFrame
            item: Item name to extract
            default: Default value if item not found

        Returns:
            Extracted value or default
        """
        try:
            if item in balance_sheet.index:
                # Get most recent value (index 0 in yfinance quarterly data)
                value = balance_sheet.loc[item].iloc[0]
                if pd.notna(value) and value is not None:
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default or 0.0
                else:
                    return default or 0.0
            else:
                return default or 0.0
        except (KeyError, IndexError, ValueError, TypeError):
            return default or 0.0

    def _extract_financial_data_from_ticker(self, ticker: str, ticker_obj) -> Optional[Dict[str, Any]]:
        """
        Extract financial data from a yfinance Ticker object.

        Args:
            ticker: Ticker symbol
            ticker_obj: yfinance Ticker object

        Returns:
            Financial data dictionary or None
        """
        try:
            ticker_info = ticker_obj.info
            if not ticker_info:
                return None

            balance_sheet = ticker_obj.quarterly_balance_sheet
            if balance_sheet is None or balance_sheet.empty:
                return None

            shares_outstanding = ticker_info.get('sharesOutstanding')
            market_cap = ticker_info.get('marketCap')

            if not shares_outstanding or not market_cap:
                return None

            # Extract balance sheet data
            total_assets = self._get_balance_sheet_value(
                balance_sheet, 'Total Assets')
            total_equity = self._get_balance_sheet_value(
                balance_sheet, 'Stockholders Equity')
            current_assets = self._get_balance_sheet_value(
                balance_sheet, 'Current Assets')

            goodwill = self._get_balance_sheet_value(
                balance_sheet, 'Goodwill', default=0)
            other_non_current = self._get_balance_sheet_value(
                balance_sheet, 'Other Non Current Assets', default=0)
            inventory = self._get_balance_sheet_value(
                balance_sheet, 'Inventory', default=0)
            other_current = self._get_balance_sheet_value(
                balance_sheet, 'Other Current Assets', default=0)

            # Get price data
            try:
                history_30d = ticker_obj.history(period="1mo")
                average_price_30d = float(history_30d['Close'].median(
                )) if not history_30d.empty else ticker_info.get('currentPrice', 0)
            except:
                average_price_30d = ticker_info.get('currentPrice', 0)

            # Calculate adjustments
            adjusted_total_assets = FinancialCalculationService.calculate_adjusted_assets(
                total_assets, goodwill, other_non_current
            )

            adjusted_current_assets = FinancialCalculationService.calculate_adjusted_current_assets(
                current_assets, inventory, other_current, inventory_adjustment_factor=0.3
            )

            return {
                'Symbol': ticker,
                'Market Cap': market_cap,
                'Shares Outstanding': shares_outstanding,
                'Total Assets': total_assets,
                'Adjusted Total Assets': adjusted_total_assets,
                'Current Assets': current_assets,
                'Adjusted Total Current Assets': adjusted_current_assets,
                'Total Equity': total_equity,
                'Average Price in Last 30 Days': average_price_30d,
                'Goodwill': goodwill,
                'Inventory': inventory,
                'Other Current Assets': other_current,
                'Other Non Current Assets': other_non_current,
            }

        except Exception as e:
            logger.error(f"Error extracting data for {ticker}: {e}")
            return None


class FinancialDataProviderFactory:
    """
    Factory for creating financial data provider instances.
    """

    @staticmethod
    def create_yfinance_provider(session=None) -> YFinanceDataProvider:
        """
        Create a YFinance data provider.

        Args:
            session: Optional requests session for yfinance

        Returns:
            Configured YFinanceDataProvider instance
        """
        return YFinanceDataProvider(session=session)

    @staticmethod
    def create_default_provider() -> YFinanceDataProvider:
        """
        Create a YFinance data provider with default settings.

        Returns:
            YFinanceDataProvider with default configuration
        """
        return YFinanceDataProvider()


# Global default provider instance for backward compatibility
_default_provider = None


def get_default_provider() -> YFinanceDataProvider:
    """
    Get the default financial data provider instance.

    Returns:
        Default YFinanceDataProvider instance
    """
    global _default_provider
    if _default_provider is None:
        _default_provider = FinancialDataProviderFactory.create_default_provider()
    return _default_provider


def get_financial_data(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get financial data for a ticker using the default provider.

    This function provides backward compatibility with the existing
    equity_calc.get_financial_data function.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Financial data dictionary or None if failed
    """
    provider = get_default_provider()
    return provider.get_financial_data(ticker)


def get_multiple_financial_data(tickers: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Get financial data for multiple tickers efficiently.

    Args:
        tickers: List of ticker symbols

    Returns:
        Dictionary mapping ticker symbols to their financial data
    """
    provider = get_default_provider()
    return provider.get_multiple_financial_data(tickers)
