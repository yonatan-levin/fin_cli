"""
Alpha Vantage data provider implementation.

This module provides financial data retrieval using the Alpha Vantage API,
offering an alternative to yfinance for fundamental and market data.
"""
import requests
import time
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime, timedelta

from fundainsight.domain.exceptions.financial_exceptions import FinancialDataRetrievalError, RateLimitError, StockNotFoundError
from shared.infrastructure.logging.log_manager import LogManager

from shared.infrastructure.utils.circuit_breaker import CircuitBreaker

logger = LogManager().get_logger("alpha_vantage_provider")


class AlphaVantageDataProvider:
    """
    Alpha Vantage data provider for financial and market data.

    Provides fundamental data, balance sheets, income statements,
    and market data using the Alpha Vantage API.
    """

    def __init__(self, api_key: str, requests_per_minute: int = 5):
        """
        Initialize the Alpha Vantage provider.

        Args:
            api_key: Alpha Vantage API key
            requests_per_minute: Rate limit for API calls
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.requests_per_minute = requests_per_minute
        self.last_request_time = 0
        self.circuit_breaker = CircuitBreaker(
            name="alpha_vantage_provider",
            failure_threshold=5,
            recovery_timeout=300,  # 5 minutes
        )

    def _rate_limit(self):
        """Implement rate limiting to respect API limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 60.0 / self.requests_per_minute

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(
                f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, params: Dict[str, str]) -> Dict[str, Any]:
        """
        Make a request to Alpha Vantage API with error handling.

        Args:
            params: Request parameters

        Returns:
            JSON response data

        Raises:
            RateLimitError: If rate limit is exceeded
            FinancialDataRetrievalError: If request fails
        """
        self._rate_limit()

        params['apikey'] = self.api_key

        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Check for Alpha Vantage specific errors
            if 'Error Message' in data:
                raise StockNotFoundError(
                    f"Alpha Vantage error: {data['Error Message']}")

            if 'Note' in data and 'API call frequency' in data['Note']:
                raise RateLimitError("Alpha Vantage rate limit exceeded")

            return data

        except requests.exceptions.RequestException as e:
            raise FinancialDataRetrievalError(
                f"Alpha Vantage API request failed: {e}")

    #@CircuitBreaker.protected
    def get_financial_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive financial data for a ticker using Alpha Vantage.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary containing financial data or None if failed
        """
        logger.info(
            f"Retrieving financial data for {symbol} from Alpha Vantage")

        try:
            # Get company overview (includes market cap, shares outstanding, etc.)
            overview = self._get_company_overview(symbol)
            if not overview:
                return None

            # Get balance sheet data
            balance_sheet = self._get_balance_sheet(symbol)
            if not balance_sheet:
                logger.warning(f"No balance sheet data available for {symbol}")
                return None

            # Get historical price data for 30-day average
            price_data = self._get_price_data(symbol, period_days=30)
            average_price_30d = self._calculate_average_price(
                price_data) if price_data else 0

            # Extract key financial metrics
            market_cap = self._safe_float(overview.get('MarketCapitalization'))
            shares_outstanding = self._safe_int(
                overview.get('SharesOutstanding'))

            if not market_cap or not shares_outstanding:
                logger.warning(f"Missing essential market data for {symbol}")
                return None

            # Extract balance sheet items (most recent quarter)
            latest_balance_sheet = balance_sheet.get('quarterlyReports', [])
            if not latest_balance_sheet:
                logger.warning(f"No quarterly balance sheet data for {symbol}")
                return None

            latest_data = latest_balance_sheet[0]  # Most recent quarter

            total_assets = self._safe_float(latest_data.get('totalAssets'))
            total_equity = self._safe_float(
                latest_data.get('totalShareholderEquity'))
            current_assets = self._safe_float(
                latest_data.get('totalCurrentAssets'))

            # Optional items for adjustments
            goodwill = self._safe_float(latest_data.get('goodwill', '0'))
            inventory = self._safe_float(latest_data.get('inventory', '0'))

            # Calculate adjusted assets
            adjusted_total_assets = total_assets - \
                goodwill if total_assets and goodwill else total_assets
            adjusted_current_assets = current_assets - \
                (inventory * 0.3) if current_assets and inventory else current_assets

            result = {
                'Ticker': symbol,
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
                'Sector': overview.get('Sector', ''),
                'Industry': overview.get('Industry', ''),
                'Country': overview.get('Country', ''),
                'data_source': 'alpha_vantage'
            }

            logger.info(
                f"Successfully retrieved financial data for {symbol} from Alpha Vantage")
            return result

        except Exception as e:
            logger.error(
                f"Failed to retrieve financial data for {symbol} from Alpha Vantage: {e}")
            return None

    def _get_company_overview(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get company overview data from Alpha Vantage."""
        try:
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol
            }
            return self._make_request(params)
        except Exception as e:
            logger.error(f"Failed to get company overview for {symbol}: {e}")
            return None

    def _get_balance_sheet(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get balance sheet data from Alpha Vantage."""
        try:
            params = {
                'function': 'BALANCE_SHEET',
                'symbol': symbol
            }
            return self._make_request(params)
        except Exception as e:
            logger.error(f"Failed to get balance sheet for {symbol}: {e}")
            return None

    def _get_price_data(self, symbol: str, period_days: int = 30) -> Optional[Dict[str, Any]]:
        """Get historical price data from Alpha Vantage."""
        try:
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'outputsize': 'compact'  # Last 100 data points
            }
            return self._make_request(params)
        except Exception as e:
            logger.error(f"Failed to get price data for {symbol}: {e}")
            return None

    def _calculate_average_price(self, price_data: Dict[str, Any]) -> float:
        """Calculate average closing price from price data."""
        try:
            time_series = price_data.get('Time Series (Daily)', {})
            if not time_series:
                return 0.0

            # Get last 30 days of data
            sorted_dates = sorted(time_series.keys(), reverse=True)[:30]
            prices = []

            for date in sorted_dates:
                close_price = float(time_series[date]['4. close'])
                prices.append(close_price)

            return sum(prices) / len(prices) if prices else 0.0

        except Exception as e:
            logger.error(f"Failed to calculate average price: {e}")
            return 0.0

    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert value to float."""
        if value is None or value == 'None' or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int."""
        if value is None or value == 'None' or value == '':
            return None
        try:
            # Convert to float first to handle scientific notation
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def get_multiple_financial_data(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get financial data for multiple symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to their financial data
        """
        logger.info(
            f"Retrieving financial data for {len(symbols)} symbols from Alpha Vantage")

        results = {}
        for symbol in symbols:
            try:
                result = self.get_financial_data(symbol)
                results[symbol] = result

                # Add delay between requests to respect rate limits
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                results[symbol] = None

        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"Successfully retrieved data for {success_count}/{len(symbols)} symbols from Alpha Vantage")

        return results

    def get_market_data(self, symbol: str, period: str = "1mo") -> Optional[pd.DataFrame]:
        """
        Get historical market data for a symbol.

        Args:
            symbol: Stock ticker symbol
            period: Period for historical data

        Returns:
            DataFrame with historical market data or None if failed
        """
        try:
            price_data = self._get_price_data(symbol)
            if not price_data:
                return None

            time_series = price_data.get('Time Series (Daily)', {})
            if not time_series:
                return None

            # Convert to DataFrame
            df_data = []
            for date_str, values in time_series.items():
                df_data.append({
                    'Date': pd.to_datetime(date_str),
                    'Open': float(values['1. open']),
                    'High': float(values['2. high']),
                    'Low': float(values['3. low']),
                    'Close': float(values['4. close']),
                    'Volume': int(values['5. volume'])
                })

            df = pd.DataFrame(df_data)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)

            # Filter by period if needed
            if period == "1mo":
                cutoff_date = datetime.now() - timedelta(days=30)
                df = df[df.index >= cutoff_date]

            logger.info(
                f"Retrieved {len(df)} days of market data for {symbol} from Alpha Vantage")
            return df

        except Exception as e:
            logger.error(
                f"Failed to retrieve market data for {symbol} from Alpha Vantage: {e}")
            return None


class AlphaVantageProviderFactory:
    """Factory for creating Alpha Vantage provider instances."""

    @staticmethod
    def create_provider(api_key: str, requests_per_minute: int = 5) -> AlphaVantageDataProvider:
        """
        Create an Alpha Vantage data provider.

        Args:
            api_key: Alpha Vantage API key
            requests_per_minute: Rate limit for API calls

        Returns:
            Configured AlphaVantageDataProvider instance
        """
        return AlphaVantageDataProvider(api_key, requests_per_minute)
