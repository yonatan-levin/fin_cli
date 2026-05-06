# Alternative Data Sources Implementation

## Overview

The AlgoBeta application now supports multiple financial data providers with intelligent fallback logic, providing resilience against rate limits, API failures, and data availability issues.

## Supported Data Providers

### 1. Yahoo Finance (yfinance) - Primary Provider
- **Status**: Default, always available
- **Cost**: Free
- **Rate Limits**: ~2000 requests/hour (unofficial)
- **Data Coverage**: Comprehensive (fundamentals, market data, historical prices)
- **Reliability**: Good, but subject to rate limiting

### 2. Alpha Vantage - Secondary Provider
- **Status**: Optional (requires API key)
- **Cost**: Free tier (5 API calls/minute, 500 calls/day)
- **Rate Limits**: 5 requests/minute (free), 75 requests/minute (premium)
- **Data Coverage**: Excellent fundamentals, good market data
- **Reliability**: Very good, stable API

### 3. IEX Cloud - Tertiary Provider
- **Status**: Optional (requires API token)
- **Cost**: Free tier (100 requests/second, 500,000 messages/month)
- **Rate Limits**: 100 requests/second (free tier)
- **Data Coverage**: Good market data, limited fundamentals
- **Reliability**: Excellent, enterprise-grade

## Architecture

### Composite Data Provider
The system uses a **Composite Data Provider** that orchestrates multiple providers:

```
CompositeDataProvider
├── YFinanceDataProvider (Priority 1 - Primary)
├── AlphaVantageDataProvider (Priority 2 - Secondary)
└── IEXCloudDataProvider (Priority 3 - Tertiary)
```

### Key Features
- **Intelligent Fallback**: Automatically tries next provider if current fails
- **Circuit Breaker Pattern**: Temporarily disables failing providers
- **Caching**: Avoids duplicate API calls with configurable TTL
- **Rate Limiting**: Respects each provider's rate limits
- **Batch Operations**: Efficient multi-symbol requests where supported
- **Comprehensive Logging**: Detailed logging for monitoring and debugging

## Configuration

### Environment Variables
Set these environment variables to enable alternative providers:

```bash
# Alpha Vantage
ALPHA_VANTAGE_API_KEY=your_api_key_here
ALPHA_VANTAGE_ENABLED=true

# IEX Cloud
IEX_CLOUD_API_TOKEN=your_token_here
IEX_CLOUD_ENABLED=true
IEX_CLOUD_IS_SANDBOX=false  # Set to true for testing

# Provider Settings
PRIMARY_PROVIDER=composite  # yfinance, alpha_vantage, iex_cloud, composite
ENABLE_FALLBACK_PROVIDERS=true
CACHE_TTL=3600  # 1 hour
```

### Configuration File
Update your configuration file:

```python
from fundainsight.infrastructure.config.settings import FinancialConfig

config = FinancialConfig(
    # Alpha Vantage settings
    alpha_vantage_api_key="your_api_key",
    alpha_vantage_enabled=True,
    alpha_vantage_rate_limit=5,  # requests per minute
    
    # IEX Cloud settings
    iex_cloud_api_token="your_token",
    iex_cloud_enabled=True,
    iex_cloud_is_sandbox=False,
    iex_cloud_rate_limit=100,  # requests per second
    
    # Provider settings
    primary_provider="composite",
    enable_fallback_providers=True,
    cache_ttl=3600,
    enable_memory_cache=True
)
```

## Usage Examples

### Basic Usage (Automatic Provider Selection)
```python
from shared.domain.services.financial_data_provider import FinancialDataProviderFactory
from fundainsight.infrastructure.config.settings import get_config

# Load configuration
config = get_config()

# Create provider (automatically selects best available)
provider = FinancialDataProviderFactory.create_provider_from_config(config)

# Get financial data (tries providers in priority order)
data = provider.get_financial_data("AAPL")
```

### Composite Provider with Manual Configuration
```python
from shared.domain.services.composite_data_provider import CompositeDataProviderFactory
from shared.domain.services.financial_data_provider import YFinanceDataProvider
from shared.domain.services.alpha_vantage_provider import AlphaVantageProviderFactory
from shared.domain.services.iex_cloud_provider import IEXCloudProviderFactory

# Create individual providers
yfinance_provider = YFinanceDataProvider()
alpha_vantage_provider = AlphaVantageProviderFactory.create_provider("your_api_key")
iex_cloud_provider = IEXCloudProviderFactory.create_provider("your_token")

# Create composite provider
composite = CompositeDataProviderFactory.create_multi_provider_composite(
    yfinance_provider=yfinance_provider,
    alpha_vantage_provider=alpha_vantage_provider,
    iex_cloud_provider=iex_cloud_provider,
    cache_ttl=3600
)

# Use composite provider
data = composite.get_financial_data("AAPL")
multiple_data = composite.get_multiple_financial_data(["AAPL", "GOOGL", "MSFT"])
```

### Monitoring Provider Performance
```python
# Get provider statistics
stats = composite.get_provider_stats()
print(stats)
# Output:
# {
#     'yfinance': {
#         'total_requests': 150,
#         'successes': 140,
#         'failures': 10,
#         'success_rate': '93.3%',
#         'circuit_breaker_open': False,
#         'last_success': 1640995200.0,
#         'last_failure': 1640991600.0
#     },
#     'alpha_vantage': {...},
#     'iex_cloud': {...}
# }

# Get cache statistics
cache_stats = composite.get_cache_stats()
print(cache_stats)
# Output:
# {
#     'total_entries': 50,
#     'expired_entries': 5,
#     'valid_entries': 45,
#     'cache_ttl': 3600
# }
```

### Manual Circuit Breaker Management
```python
# Reset all circuit breakers
composite.reset_circuit_breakers()

# Clear cache
composite.clear_cache()
```

## API Key Setup

### Alpha Vantage
1. Visit [Alpha Vantage](https://www.alphavantage.co/support/#api-key)
2. Sign up for a free account
3. Get your API key
4. Set environment variable: `ALPHA_VANTAGE_API_KEY=your_key`

### IEX Cloud
1. Visit [IEX Cloud](https://iexcloud.io/console/)
2. Sign up for a free account
3. Get your API token
4. Set environment variable: `IEX_CLOUD_API_TOKEN=your_token`
5. For production, set: `IEX_CLOUD_IS_SANDBOX=false`

## Error Handling

### Circuit Breaker Pattern
When a provider fails repeatedly (default: 5 failures), it's temporarily disabled:

```python
# Circuit breaker opens after 5 failures
# Provider is disabled for 5 minutes (300 seconds)
# Automatically resets after timeout or successful request
```

### Fallback Logic
1. Try primary provider (yfinance)
2. If fails, try secondary provider (Alpha Vantage)
3. If fails, try tertiary provider (IEX Cloud)
4. If all fail, return None

### Rate Limit Handling
- Each provider implements its own rate limiting
- Automatic retry with exponential backoff
- Circuit breaker opens on repeated rate limit errors

## Performance Optimization

### Caching Strategy
- **Memory Cache**: Fast, in-memory storage with TTL
- **Default TTL**: 1 hour (3600 seconds)
- **Cache Key**: Stock symbol
- **Cache Invalidation**: Automatic based on TTL

### Batch Operations
- Use `get_multiple_financial_data()` for multiple symbols
- Providers that support batch operations are used first
- Falls back to individual requests for remaining symbols

### Rate Limit Distribution
- Requests are distributed across providers
- Failed providers are temporarily disabled
- Reduces load on any single provider

## Monitoring and Logging

### Log Levels
- **INFO**: Successful requests, provider selection
- **WARNING**: Provider failures, fallbacks
- **ERROR**: All providers failed, critical errors
- **DEBUG**: Rate limiting, circuit breaker state changes

### Key Metrics to Monitor
- Provider success rates
- Circuit breaker status
- Cache hit rates
- Request latency
- Rate limit violations

### Example Log Output
```
2024-01-01 10:00:00 INFO [composite_data_provider] Retrieving financial data for AAPL
2024-01-01 10:00:00 DEBUG [composite_data_provider] Trying provider yfinance for AAPL
2024-01-01 10:00:01 INFO [composite_data_provider] Successfully retrieved data for AAPL from yfinance
2024-01-01 10:00:05 WARNING [composite_data_provider] Provider yfinance failed for GOOGL: Rate limit exceeded
2024-01-01 10:00:05 DEBUG [composite_data_provider] Trying provider alpha_vantage for GOOGL
2024-01-01 10:00:06 INFO [composite_data_provider] Successfully retrieved data for GOOGL from alpha_vantage
```

## Best Practices

### 1. Configuration
- Always configure multiple providers for resilience
- Use environment variables for API keys
- Set appropriate rate limits based on your plan

### 2. Error Handling
- Always check for None return values
- Implement retry logic in your application
- Monitor circuit breaker status

### 3. Performance
- Use batch operations for multiple symbols
- Configure appropriate cache TTL
- Monitor provider performance regularly

### 4. Security
- Never commit API keys to version control
- Use environment variables or secure configuration
- Rotate API keys regularly

## Troubleshooting

### Common Issues

#### 1. "No data returned from any provider"
- Check API keys are correctly set
- Verify providers are enabled in configuration
- Check rate limits haven't been exceeded
- Verify stock symbol is valid

#### 2. "Circuit breaker open for provider"
- Provider has failed repeatedly
- Wait for timeout (default: 5 minutes) or reset manually
- Check provider status and API limits

#### 3. "Rate limit exceeded"
- Reduce request frequency
- Use caching to avoid duplicate requests
- Consider upgrading to paid API plans

#### 4. "Import errors for providers"
- Install required dependencies: `pip install requests pandas`
- Check Python path and module imports

### Debug Commands
```python
# Check provider status
stats = composite.get_provider_stats()
for name, stat in stats.items():
    print(f"{name}: {stat['success_rate']} success rate")

# Reset failing providers
composite.reset_circuit_breakers()

# Clear cache to force fresh requests
composite.clear_cache()

# Test individual providers
data = yfinance_provider.get_financial_data("AAPL")
data = alpha_vantage_provider.get_financial_data("AAPL")
data = iex_cloud_provider.get_financial_data("AAPL")
```

## Migration Guide

### From Single Provider (yfinance only)
1. Update configuration to enable alternative providers
2. Add API keys for Alpha Vantage and/or IEX Cloud
3. Change provider creation to use composite provider
4. Test with a few symbols before full deployment

### Gradual Migration
1. Start with yfinance + one alternative provider
2. Monitor performance and error rates
3. Add additional providers as needed
4. Adjust rate limits and cache settings based on usage

## Future Enhancements

### Planned Features
- **Polygon.io Provider**: High-quality market data
- **Financial Modeling Prep**: Comprehensive fundamentals
- **Quandl/Nasdaq Data Link**: Economic and financial data
- **Database Caching**: Persistent cache with SQLite/PostgreSQL
- **Provider Health Checks**: Automated provider status monitoring
- **Load Balancing**: Intelligent request distribution
- **Metrics Dashboard**: Real-time provider performance monitoring

### Configuration for Future Providers
The architecture is designed to easily add new providers:

```python
# Example: Adding a new provider
new_provider = NewProviderFactory.create_provider(api_key="key")
config = ProviderConfig(
    name="new_provider",
    provider=new_provider,
    priority=ProviderPriority.FALLBACK,
    enabled=True
)
composite.add_provider(config)
```

## Conclusion

The alternative data sources implementation provides:
- **Resilience**: Multiple providers with automatic fallback
- **Performance**: Caching and batch operations
- **Monitoring**: Comprehensive logging and statistics
- **Flexibility**: Easy configuration and provider management
- **Scalability**: Circuit breakers and rate limiting

This ensures your financial data retrieval remains robust and reliable even when individual providers experience issues. 