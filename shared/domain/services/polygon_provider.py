"""
Polygon.io Financial Data Provider.

This module provides integration with the Polygon.io REST API for financial data.
Polygon.io offers real-time and historical financial market data.
"""
import time
import requests
from typing import Optional, Dict, Any, List
from dataclasses import field
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd

from shared.infrastructure.logging.log_manager import LogManager
from shared.infrastructure.utils.user_agent_rotator import get_random_headers
from .financial_calculation_service import FinancialCalculationService

logger = LogManager().get_logger("polygon_provider")


@dataclass
class PolygonRateLimiter:
    """Rate limiter for Polygon.io API calls."""

    requests_per_minute: int = 5  # Free tier limit
    _request_times: List[float] = field(default_factory=list)

    def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.requests_per_minute:
            # Wait until the oldest request is over 1 minute old
            wait_time = 60 - (now - self._request_times[0]) + 1
            if wait_time > 0:
                logger.info(
                    f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                # Clean up old requests after waiting
                now = time.time()
                self._request_times = [
                    t for t in self._request_times if now - t < 60]

        self._request_times.append(now)


class PolygonDataProvider:
    """
    Financial data provider using Polygon.io API.

    This provider offers comprehensive financial data including:
    - Company fundamentals and financials
    - Real-time and historical market data
    - Market indicators and reference data
    """

    def __init__(self, api_key: str, requests_per_minute: int = 5):
        """
        Initialize the Polygon data provider.

        Args:
            api_key: Polygon.io API key
            requests_per_minute: Rate limit for API calls (default: 5 for free tier)
        """
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        self.rate_limiter = PolygonRateLimiter(
            requests_per_minute=requests_per_minute)
        self.session = requests.Session()
        self.session.headers.update(get_random_headers())

        # Provider statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'rate_limited_requests': 0,
            'total_response_time': 0.0
        }

    def get_financial_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive financial data for a ticker using Polygon.io.

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary containing financial data or None if failed
        """
        logger.info(f"Retrieving financial data for {ticker} from Polygon.io")

        try:
            # Get company details
            company_info = self._get_company_details(ticker)
            if not company_info:
                logger.warning(f"No company info available for {ticker}")
                return None

            # Get financial data
            financials = self._get_company_financials(ticker)
            if not financials:
                logger.warning(f"No financial data available for {ticker}")
                return None

            # Get market data
            market_data = self._get_market_data(ticker)

            # Combine and structure the data
            result = self._structure_financial_data(
                ticker, company_info, financials, market_data)

            if result:
                logger.info(
                    f"Successfully retrieved financial data for {ticker} from Polygon.io")
                return result
            else:
                logger.warning(
                    f"Could not structure financial data for {ticker}")
                return None

        except Exception as e:
            logger.error(
                f"Failed to retrieve financial data for {ticker} from Polygon.io: {e}")
            return None

    def _get_company_details(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get company details from Polygon."""
        endpoint = f"/v3/reference/tickers/{ticker}"
        return self._make_api_call(endpoint)

    def _get_company_financials(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get company financial statements from Polygon."""
        endpoint = f"/vX/reference/financials"
        params = {
            'ticker': ticker,
            'timeframe': 'quarterly',
            'limit': 4  # Get last 4 quarters
        }
        return self._make_api_call(endpoint, params)

    def _get_market_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Get recent market data for the ticker."""
        try:
            # Get aggregates for the last 30 days
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            endpoint = f"/v2/aggs/ticker/{ticker}/range/1/day/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            params = {
                'adjusted': 'true',
                'sort': 'asc'
            }

            response = self._make_api_call(endpoint, params)
            if response and 'results' in response:
                # Calculate average price from the results
                prices = [bar['c']
                          for bar in response['results']]  # closing prices
                if prices:
                    return {
                        'average_price_30d': sum(prices) / len(prices),
                        'current_price': prices[-1] if prices else None,
                        'price_data_points': len(prices)
                    }

            return None

        except Exception as e:
            logger.warning(f"Could not get market data for {ticker}: {e}")
            return None

    def _structure_financial_data(self, ticker: str, company_info: Dict, financials: Dict, market_data: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Structure the data into our standard format."""
        try:
            # Extract company information
            company_details = company_info.get('results', {})
            market_cap = company_details.get('market_cap')
            shares_outstanding = company_details.get(
                'share_class_shares_outstanding')

            if not market_cap or not shares_outstanding:
                logger.warning(f"Missing essential market data for {ticker}")
                return None

            # Extract financial data from the most recent quarter
            financial_results = financials.get('results', [])
            if not financial_results:
                logger.warning(f"No financial results for {ticker}")
                return None

            # Get the most recent financials
            latest_financials = financial_results[0].get('financials', {})
            balance_sheet = latest_financials.get('balance_sheet', {})

            # Extract balance sheet items
            total_assets = balance_sheet.get('assets', {}).get('value', 0)
            current_assets = balance_sheet.get(
                'current_assets', {}).get('value', 0)
            total_equity = balance_sheet.get('equity', {}).get('value', 0)

            # Optional items for adjustments
            goodwill = balance_sheet.get('goodwill', {}).get('value', 0)
            inventory = balance_sheet.get('inventory', {}).get('value', 0)

            # Get market price data
            average_price_30d = 0
            if market_data:
                average_price_30d = market_data.get('average_price_30d', 0)

            # Calculate adjusted assets using domain service
            adjusted_total_assets = FinancialCalculationService.calculate_adjusted_assets(
                total_assets, goodwill, 0  # No other non-current assets in Polygon data
            )

            adjusted_current_assets = FinancialCalculationService.calculate_adjusted_current_assets(
                current_assets, inventory, 0, inventory_adjustment_factor=0.3
            )

            return {
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
                'Other Current Assets': 0,
                'Other Non Current Assets': 0,
                'Data Source': 'Polygon.io'
            }

        except Exception as e:
            logger.error(f"Error structuring financial data for {ticker}: {e}")
            return None

    def _make_api_call(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        """Make an API call to Polygon with rate limiting and error handling."""
        self.rate_limiter.wait_if_needed()

        url = f"{self.base_url}{endpoint}"
        if params is None:
            params = {}

        params['apikey'] = self.api_key

        self.stats['total_requests'] += 1
        start_time = time.time()

        try:
            # Rotate user agent for this request
            self.session.headers.update(get_random_headers())

            response = self.session.get(url, params=params, timeout=30)
            response_time = time.time() - start_time
            self.stats['total_response_time'] += response_time

            if response.status_code == 200:
                self.stats['successful_requests'] += 1
                data = response.json()

                # Check if the response indicates success
                if data.get('status') == 'OK':
                    return data
                else:
                    logger.warning(
                        f"Polygon API returned non-OK status: {data.get('status')}")
                    return None

            elif response.status_code == 429:
                # Rate limited
                self.stats['rate_limited_requests'] += 1
                logger.warning("Rate limited by Polygon.io API")
                time.sleep(60)  # Wait 1 minute
                return None

            else:
                self.stats['failed_requests'] += 1
                logger.error(
                    f"Polygon API error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            self.stats['failed_requests'] += 1
            logger.error(f"Timeout calling Polygon API: {url}")
            return None

        except Exception as e:
            self.stats['failed_requests'] += 1
            logger.error(f"Error calling Polygon API: {e}")
            return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get provider performance statistics."""
        avg_response_time = (
            self.stats['total_response_time'] /
            max(self.stats['successful_requests'], 1)
        )

        return {
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests'],
            'rate_limited_requests': self.stats['rate_limited_requests'],
            'success_rate': (self.stats['successful_requests'] / max(self.stats['total_requests'], 1)) * 100,
            'average_response_time': avg_response_time
        }


class PolygonProviderFactory:
    """Factory for creating Polygon data provider instances."""

    @staticmethod
    def create_provider(api_key: str, requests_per_minute: int = 5) -> PolygonDataProvider:
        """
        Create a Polygon data provider.

        Args:
            api_key: Polygon.io API key
            requests_per_minute: Rate limit for API calls

        Returns:
            Configured PolygonDataProvider instance
        """
        return PolygonDataProvider(
            api_key=api_key,
            requests_per_minute=requests_per_minute
        )
