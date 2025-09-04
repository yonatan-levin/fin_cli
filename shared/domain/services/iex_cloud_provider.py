"""
IEX Cloud data provider implementation.

This module provides financial data retrieval using the IEX Cloud API,
offering an alternative to yfinance for market and fundamental data.
"""
import requests
import time
from typing import Optional, Dict, Any, List
import pandas as pd
from datetime import datetime, timedelta

from shared.infrastructure.logging.log_manager import LogManager
from fundainsight.domain.exceptions.financial_exceptions import FinancialDataRetrievalError, RateLimitError, StockNotFoundError
from shared.infrastructure.utils.circuit_breaker import CircuitBreaker

logger = LogManager().get_logger("iex_cloud_provider")


class IEXCloudDataProvider:
    """
    IEX Cloud data provider for financial and market data.

    Provides market data, company information, and some fundamental data
    using the IEX Cloud API.
    """

    def __init__(self, api_token: str, is_sandbox: bool = False, requests_per_second: int = 100):
        """
        Initialize the IEX Cloud provider.

        Args:
            api_token: IEX Cloud API token
            is_sandbox: Whether to use sandbox environment
            requests_per_second: Rate limit for API calls
        """
        self.api_token = api_token
        self.is_sandbox = is_sandbox
        self.base_url = "https://sandbox.iexapis.com/stable" if is_sandbox else "https://cloud.iexapis.com/stable"
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
        self.circuit_breaker = CircuitBreaker(
            name="iex_cloud_provider",
            failure_threshold=5,
            recovery_timeout=300,  # 5 minutes
        )

    def _rate_limit(self):
        """Implement rate limiting to respect API limits."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(
                f"Rate limiting: sleeping for {sleep_time:.3f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Make a request to IEX Cloud API with error handling.

        Args:
            endpoint: API endpoint
            params: Optional request parameters

        Returns:
            JSON response data

        Raises:
            RateLimitError: If rate limit is exceeded
            FinancialDataRetrievalError: If request fails
        """
        self._rate_limit()

        url = f"{self.base_url}/{endpoint}"
        request_params = params or {}
        request_params['token'] = self.api_token

        try:
            response = requests.get(url, params=request_params, timeout=30)

            if response.status_code == 429:
                raise RateLimitError("IEX Cloud rate limit exceeded")
            elif response.status_code == 404:
                raise StockNotFoundError("Symbol not found in IEX Cloud")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise FinancialDataRetrievalError(
                f"IEX Cloud API request failed: {e}")

    #@CircuitBreaker.protected
    def get_financial_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive financial data for a ticker using IEX Cloud.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary containing financial data or None if failed
        """
        logger.info(f"Retrieving financial data for {symbol} from IEX Cloud")

        try:
            # Get company information
            company_info = self._get_company_info(symbol)
            if not company_info:
                return None

            # Get key stats (includes market cap, shares outstanding, etc.)
            key_stats = self._get_key_stats(symbol)
            if not key_stats:
                logger.warning(f"No key stats available for {symbol}")
                return None

            # Get balance sheet data
            balance_sheet = self._get_balance_sheet(symbol)

            # Get historical price data for 30-day average
            price_data = self._get_price_data(symbol, range_period="1m")
            average_price_30d = self._calculate_average_price(
                price_data) if price_data else 0

            # Extract key financial metrics
            market_cap = key_stats.get('marketcap')
            shares_outstanding = key_stats.get('sharesOutstanding')

            if not market_cap or not shares_outstanding:
                logger.warning(f"Missing essential market data for {symbol}")
                return None

            # Extract balance sheet items if available
            total_assets = None
            total_equity = None
            current_assets = None
            goodwill = 0
            inventory = 0

            if balance_sheet and balance_sheet.get('balancesheet'):
                latest_bs = balance_sheet['balancesheet'][0] if balance_sheet['balancesheet'] else {
                }
                total_assets = latest_bs.get('totalAssets')
                total_equity = latest_bs.get('shareholderEquity')
                current_assets = latest_bs.get('currentAssets')
                goodwill = latest_bs.get('goodwill', 0) or 0
                inventory = latest_bs.get('inventory', 0) or 0

            # Calculate adjusted assets if we have the data
            adjusted_total_assets = None
            adjusted_current_assets = None

            if total_assets:
                adjusted_total_assets = total_assets - goodwill

            if current_assets:
                adjusted_current_assets = current_assets - (inventory * 0.3)

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
                'Sector': company_info.get('sector', ''),
                'Industry': company_info.get('industry', ''),
                'Country': company_info.get('country', ''),
                'data_source': 'iex_cloud'
            }

            logger.info(
                f"Successfully retrieved financial data for {symbol} from IEX Cloud")
            return result

        except Exception as e:
            logger.error(
                f"Failed to retrieve financial data for {symbol} from IEX Cloud: {e}")
            return None

    def _get_company_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get company information from IEX Cloud."""
        try:
            return self._make_request(f"stock/{symbol}/company")
        except Exception as e:
            logger.error(f"Failed to get company info for {symbol}: {e}")
            return None

    def _get_key_stats(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get key statistics from IEX Cloud."""
        try:
            return self._make_request(f"stock/{symbol}/stats")
        except Exception as e:
            logger.error(f"Failed to get key stats for {symbol}: {e}")
            return None

    def _get_balance_sheet(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get balance sheet data from IEX Cloud."""
        try:
            return self._make_request(f"stock/{symbol}/balance-sheet")
        except Exception as e:
            logger.warning(f"Balance sheet not available for {symbol}: {e}")
            return None

    def _get_price_data(self, symbol: str, range_period: str = "1m") -> Optional[List[Dict[str, Any]]]:
        """Get historical price data from IEX Cloud."""
        try:
            return self._make_request(f"stock/{symbol}/chart/{range_period}")
        except Exception as e:
            logger.error(f"Failed to get price data for {symbol}: {e}")
            return None

    def _calculate_average_price(self, price_data: List[Dict[str, Any]]) -> float:
        """Calculate average closing price from price data."""
        try:
            if not price_data:
                return 0.0

            # Get last 30 days of data
            recent_data = price_data[-30:] if len(
                price_data) >= 30 else price_data
            prices = [day['close'] for day in recent_data if day.get('close')]

            return sum(prices) / len(prices) if prices else 0.0

        except Exception as e:
            logger.error(f"Failed to calculate average price: {e}")
            return 0.0

    def get_multiple_financial_data(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get financial data for multiple symbols.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to their financial data
        """
        logger.info(
            f"Retrieving financial data for {len(symbols)} symbols from IEX Cloud")

        results = {}
        for symbol in symbols:
            try:
                result = self.get_financial_data(symbol)
                results[symbol] = result

            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                results[symbol] = None

        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"Successfully retrieved data for {success_count}/{len(symbols)} symbols from IEX Cloud")

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
            # Map period to IEX Cloud range
            range_mapping = {
                "1mo": "1m",
                "3mo": "3m",
                "6mo": "6m",
                "1y": "1y",
                "2y": "2y",
                "5y": "5y"
            }

            iex_range = range_mapping.get(period, "1m")
            price_data = self._get_price_data(symbol, iex_range)

            if not price_data:
                return None

            # Convert to DataFrame
            df_data = []
            for day in price_data:
                if all(key in day for key in ['date', 'open', 'high', 'low', 'close', 'volume']):
                    df_data.append({
                        'Date': pd.to_datetime(day['date']),
                        'Open': day['open'],
                        'High': day['high'],
                        'Low': day['low'],
                        'Close': day['close'],
                        'Volume': day['volume']
                    })

            if not df_data:
                return None

            df = pd.DataFrame(df_data)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)

            logger.info(
                f"Retrieved {len(df)} days of market data for {symbol} from IEX Cloud")
            return df

        except Exception as e:
            logger.error(
                f"Failed to retrieve market data for {symbol} from IEX Cloud: {e}")
            return None

    def get_batch_quotes(self, symbols: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get batch quotes for multiple symbols efficiently.

        Args:
            symbols: List of ticker symbols

        Returns:
            Dictionary mapping symbols to their quote data
        """
        try:
            symbols_str = ','.join(symbols)
            endpoint = f"stock/market/batch"
            params = {
                'symbols': symbols_str,
                'types': 'quote,stats,company'
            }

            batch_data = self._make_request(endpoint, params)

            results = {}
            for symbol in symbols:
                symbol_data = batch_data.get(symbol)
                if symbol_data:
                    quote = symbol_data.get('quote', {})
                    stats = symbol_data.get('stats', {})
                    company = symbol_data.get('company', {})

                    results[symbol] = {
                        'symbol': symbol,
                        'price': quote.get('latestPrice'),
                        'market_cap': stats.get('marketcap'),
                        'pe_ratio': quote.get('peRatio'),
                        'sector': company.get('sector'),
                        'industry': company.get('industry')
                    }
                else:
                    results[symbol] = None

            return results

        except Exception as e:
            logger.error(f"Failed to get batch quotes: {e}")
            return {symbol: None for symbol in symbols}


class IEXCloudProviderFactory:
    """Factory for creating IEX Cloud provider instances."""

    @staticmethod
    def create_provider(api_token: str, is_sandbox: bool = False, requests_per_second: int = 100) -> IEXCloudDataProvider:
        """
        Create an IEX Cloud data provider.

        Args:
            api_token: IEX Cloud API token
            is_sandbox: Whether to use sandbox environment
            requests_per_second: Rate limit for API calls

        Returns:
            Configured IEXCloudDataProvider instance
        """
        return IEXCloudDataProvider(api_token, is_sandbox, requests_per_second)
