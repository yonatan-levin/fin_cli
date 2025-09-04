"""
Composite data provider implementation.

This module provides a unified interface that orchestrates multiple financial data providers
with intelligent fallback logic, caching, and resilience patterns.
"""
import time
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
from dataclasses import dataclass
import pandas as pd

from shared.infrastructure.logging.log_manager import LogManager

class RateLimitError(Exception):
    """Raised when API rate limit is exceeded."""
    pass


logger = LogManager().get_logger("composite_data_provider")


class ProviderPriority(Enum):
    """Provider priority levels."""
    PRIMARY = 1
    SECONDARY = 2
    TERTIARY = 3
    FALLBACK = 4


@dataclass
class ProviderConfig:
    """Configuration for a data provider."""
    name: str
    provider: Any  # The actual provider instance
    priority: ProviderPriority
    enabled: bool = True
    max_retries: int = 2
    retry_delay: float = 1.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: int = 300  # 5 minutes


class CompositeDataProvider:
    """
    Composite data provider that orchestrates multiple providers with fallback logic.

    Features:
    - Intelligent provider selection based on priority and availability
    - Automatic fallback to secondary providers on failure
    - Circuit breaker pattern for failed providers
    - Caching to avoid duplicate API calls
    - Rate limiting across providers
    - Comprehensive error handling and logging
    """

    def __init__(self, cache_ttl: int = 3600):
        """
        Initialize the composite provider.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 1 hour)
        """
        self.providers: List[ProviderConfig] = []
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl
        self.provider_stats: Dict[str, Dict[str, Any]] = {}

    def add_provider(self, config: ProviderConfig):
        """
        Add a data provider to the composite.

        Args:
            config: Provider configuration
        """
        self.providers.append(config)
        self.providers.sort(key=lambda x: x.priority.value)

        # Initialize stats for this provider
        self.provider_stats[config.name] = {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'last_success': None,
            'last_failure': None,
            'circuit_breaker_open': False,
            'circuit_breaker_open_until': None
        }

        logger.info(
            f"Added provider {config.name} with priority {config.priority.name}")

    def get_financial_data(self, symbol: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive financial data for a ticker using the best available provider.

        Args:
            symbol: Stock ticker symbol
            force_refresh: Whether to bypass cache and force fresh data

        Returns:
            Dictionary containing financial data or None if all providers failed
        """
        logger.info(f"Retrieving financial data for {symbol}")

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_data = self._get_from_cache(symbol)
            if cached_data:
                logger.info(f"Using cached data for {symbol}")
                return cached_data

        # Try providers in priority order
        for provider_config in self._get_available_providers():
            try:
                logger.debug(
                    f"Trying provider {provider_config.name} for {symbol}")

                # Check circuit breaker
                if self._is_circuit_breaker_open(provider_config.name):
                    logger.debug(
                        f"Circuit breaker open for {provider_config.name}, skipping")
                    continue

                # Attempt to get data with retries
                data = self._get_data_with_retries(provider_config, symbol)

                if data:
                    # Success - update stats and cache
                    self._record_success(provider_config.name)
                    self._save_to_cache(symbol, data)

                    logger.info(
                        f"Successfully retrieved data for {symbol} from {provider_config.name}")
                    return data
                else:
                    # Provider returned None - try next provider
                    self._record_failure(
                        provider_config.name, "No data returned")
                    continue

            except Exception as e:
                # Provider failed - record failure and try next
                self._record_failure(provider_config.name, str(e))
                logger.warning(
                    f"Provider {provider_config.name} failed for {symbol}: {e}")
                continue

        # All providers failed
        logger.error(f"All providers failed to retrieve data for {symbol}")
        return None

    def get_multiple_financial_data(self, symbols: List[str], force_refresh: bool = False) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Get financial data for multiple symbols efficiently.

        Args:
            symbols: List of ticker symbols
            force_refresh: Whether to bypass cache and force fresh data

        Returns:
            Dictionary mapping symbols to their financial data
        """
        logger.info(f"Retrieving financial data for {len(symbols)} symbols")

        results = {}

        # Check cache for all symbols first
        uncached_symbols = []
        if not force_refresh:
            for symbol in symbols:
                cached_data = self._get_from_cache(symbol)
                if cached_data:
                    results[symbol] = cached_data
                else:
                    uncached_symbols.append(symbol)
        else:
            uncached_symbols = symbols.copy()

        if not uncached_symbols:
            logger.info("All symbols found in cache")
            return results

        logger.info(
            f"Need to fetch {len(uncached_symbols)} symbols from providers")

        # Try to get batch data from providers that support it
        remaining_symbols = uncached_symbols.copy()

        for provider_config in self._get_available_providers():
            if not remaining_symbols:
                break

            try:
                if self._is_circuit_breaker_open(provider_config.name):
                    continue

                # Check if provider supports batch operations
                if hasattr(provider_config.provider, 'get_multiple_financial_data'):
                    logger.debug(
                        f"Using batch operation from {provider_config.name}")
                    batch_results = provider_config.provider.get_multiple_financial_data(
                        remaining_symbols)

                    # Process batch results
                    successful_symbols = []
                    for symbol, data in batch_results.items():
                        if data:
                            results[symbol] = data
                            self._save_to_cache(symbol, data)
                            successful_symbols.append(symbol)

                    # Remove successful symbols from remaining
                    remaining_symbols = [
                        s for s in remaining_symbols if s not in successful_symbols]

                    if successful_symbols:
                        self._record_success(provider_config.name)
                        logger.info(
                            f"Provider {provider_config.name} successfully retrieved {len(successful_symbols)} symbols")

            except Exception as e:
                self._record_failure(provider_config.name, str(e))
                logger.warning(
                    f"Batch operation failed for {provider_config.name}: {e}")

        # For remaining symbols, try individual requests
        for symbol in remaining_symbols:
            data = self.get_financial_data(symbol, force_refresh=True)
            results[symbol] = data

        success_count = sum(1 for v in results.values() if v is not None)
        logger.info(
            f"Successfully retrieved data for {success_count}/{len(symbols)} symbols")

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
        logger.info(f"Retrieving market data for {symbol} (period: {period})")

        for provider_config in self._get_available_providers():
            try:
                if self._is_circuit_breaker_open(provider_config.name):
                    continue

                if hasattr(provider_config.provider, 'get_market_data'):
                    data = provider_config.provider.get_market_data(
                        symbol, period)
                    if data is not None and not data.empty:
                        self._record_success(provider_config.name)
                        logger.info(
                            f"Retrieved market data for {symbol} from {provider_config.name}")
                        return data

            except Exception as e:
                self._record_failure(provider_config.name, str(e))
                logger.warning(
                    f"Market data request failed for {provider_config.name}: {e}")

        logger.error(
            f"All providers failed to retrieve market data for {symbol}")
        return None

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all providers.

        Returns:
            Dictionary with provider statistics
        """
        stats = {}
        for name, provider_stats in self.provider_stats.items():
            total_requests = provider_stats['requests']
            success_rate = (
                provider_stats['successes'] / total_requests * 100) if total_requests > 0 else 0

            stats[name] = {
                'total_requests': total_requests,
                'successes': provider_stats['successes'],
                'failures': provider_stats['failures'],
                'success_rate': f"{success_rate:.1f}%",
                'circuit_breaker_open': provider_stats['circuit_breaker_open'],
                'last_success': provider_stats['last_success'],
                'last_failure': provider_stats['last_failure']
            }

        return stats

    def reset_circuit_breakers(self):
        """Reset all circuit breakers manually."""
        for name in self.provider_stats:
            self.provider_stats[name]['circuit_breaker_open'] = False
            self.provider_stats[name]['circuit_breaker_open_until'] = None
        logger.info("All circuit breakers have been reset")

    def _get_available_providers(self) -> List[ProviderConfig]:
        """Get list of enabled providers sorted by priority."""
        return [p for p in self.providers if p.enabled]

    def _get_data_with_retries(self, provider_config: ProviderConfig, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get data from a provider with retry logic.

        Args:
            provider_config: Provider configuration
            symbol: Stock ticker symbol

        Returns:
            Financial data or None if failed
        """
        last_exception = None

        for attempt in range(provider_config.max_retries + 1):
            try:
                self.provider_stats[provider_config.name]['requests'] += 1

                # Call the provider's get_financial_data method
                data = provider_config.provider.get_financial_data(symbol)
                return data

            except RateLimitError as e:
                last_exception = e
                if attempt < provider_config.max_retries:
                    delay = provider_config.retry_delay * \
                        (2 ** attempt)  # Exponential backoff
                    logger.debug(
                        f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1})")
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                last_exception = e
                if attempt < provider_config.max_retries:
                    delay = provider_config.retry_delay
                    logger.debug(
                        f"Request failed, retrying in {delay}s (attempt {attempt + 1}): {e}")
                    time.sleep(delay)
                else:
                    raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        return None

    def _is_circuit_breaker_open(self, provider_name: str) -> bool:
        """Check if circuit breaker is open for a provider."""
        stats = self.provider_stats[provider_name]

        if not stats['circuit_breaker_open']:
            return False

        # Check if timeout has expired
        if stats['circuit_breaker_open_until'] and time.time() > stats['circuit_breaker_open_until']:
            stats['circuit_breaker_open'] = False
            stats['circuit_breaker_open_until'] = None
            logger.info(
                f"Circuit breaker for {provider_name} has been reset after timeout")
            return False

        return True

    def _record_success(self, provider_name: str):
        """Record a successful request for a provider."""
        stats = self.provider_stats[provider_name]
        stats['successes'] += 1
        stats['last_success'] = time.time()

        # Reset circuit breaker on success
        if stats['circuit_breaker_open']:
            stats['circuit_breaker_open'] = False
            stats['circuit_breaker_open_until'] = None
            logger.info(
                f"Circuit breaker for {provider_name} reset after successful request")

    def _record_failure(self, provider_name: str, error_message: str):
        """Record a failed request for a provider."""
        stats = self.provider_stats[provider_name]
        stats['failures'] += 1
        stats['last_failure'] = time.time()

        # Check if we should open circuit breaker
        provider_config = next(
            (p for p in self.providers if p.name == provider_name), None)
        if provider_config and stats['failures'] >= provider_config.circuit_breaker_threshold:
            stats['circuit_breaker_open'] = True
            stats['circuit_breaker_open_until'] = time.time(
            ) + provider_config.circuit_breaker_timeout
            logger.warning(
                f"Circuit breaker opened for {provider_name} due to {stats['failures']} failures")

    def _get_from_cache(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get data from cache if available and not expired."""
        if symbol not in self.cache:
            return None

        cache_entry = self.cache[symbol]
        if time.time() - cache_entry['timestamp'] > self.cache_ttl:
            # Cache expired
            del self.cache[symbol]
            return None

        return cache_entry['data']

    def _save_to_cache(self, symbol: str, data: Dict[str, Any]):
        """Save data to cache with timestamp."""
        self.cache[symbol] = {
            'data': data,
            'timestamp': time.time()
        }

    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        logger.info("Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.cache)
        expired_entries = 0

        current_time = time.time()
        for entry in self.cache.values():
            if current_time - entry['timestamp'] > self.cache_ttl:
                expired_entries += 1

        return {
            'total_entries': total_entries,
            'expired_entries': expired_entries,
            'valid_entries': total_entries - expired_entries,
            'cache_ttl': self.cache_ttl
        }


class CompositeDataProviderFactory:
    """Factory for creating composite data provider instances."""

    @staticmethod
    def create_default_composite() -> CompositeDataProvider:
        """
        Create a composite provider with default configuration.

        Returns:
            CompositeDataProvider with yfinance as primary provider
        """
        from shared.domain.services.financial_data_provider import YFinanceDataProvider

        composite = CompositeDataProvider(cache_ttl=3600)  # 1 hour cache

        # Add yfinance as primary provider
        yfinance_provider = YFinanceDataProvider()
        yfinance_config = ProviderConfig(
            name="yfinance",
            provider=yfinance_provider,
            priority=ProviderPriority.PRIMARY,
            enabled=True,
            max_retries=3,
            retry_delay=2.0
        )
        composite.add_provider(yfinance_config)

        return composite

    @staticmethod
    def create_multi_provider_composite(
        yfinance_provider=None,
        alpha_vantage_provider=None,
        iex_cloud_provider=None,
        polygon_provider=None,
        cache_ttl: int = 3600
    ) -> CompositeDataProvider:
        """
        Create a composite provider with multiple data sources.

        Args:
            yfinance_provider: YFinance provider instance
            alpha_vantage_provider: Alpha Vantage provider instance
            iex_cloud_provider: IEX Cloud provider instance
            polygon_provider: Polygon.io provider instance
            cache_ttl: Cache time-to-live in seconds

        Returns:
            CompositeDataProvider with multiple providers configured
        """
        composite = CompositeDataProvider(cache_ttl=cache_ttl)

        # Add providers in priority order
        if yfinance_provider:
            config = ProviderConfig(
                name="yfinance",
                provider=yfinance_provider,
                priority=ProviderPriority.PRIMARY,
                enabled=True,
                max_retries=3,
                retry_delay=2.0
            )
            composite.add_provider(config)

        if alpha_vantage_provider:
            config = ProviderConfig(
                name="alpha_vantage",
                provider=alpha_vantage_provider,
                priority=ProviderPriority.SECONDARY,
                enabled=True,
                max_retries=2,
                retry_delay=1.0
            )
            composite.add_provider(config)

        if iex_cloud_provider:
            config = ProviderConfig(
                name="iex_cloud",
                provider=iex_cloud_provider,
                priority=ProviderPriority.TERTIARY,
                enabled=True,
                max_retries=2,
                retry_delay=0.5
            )
            composite.add_provider(config)

        if polygon_provider:
            config = ProviderConfig(
                name="polygon",
                provider=polygon_provider,
                priority=ProviderPriority.FALLBACK,
                enabled=True,
                max_retries=2,
                retry_delay=1.0
            )
            composite.add_provider(config)

        return composite
