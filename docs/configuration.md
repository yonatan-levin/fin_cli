# FinPack Configuration Guide

This guide explains how to configure FinPack for different use cases and environments.

## Table of Contents

- [Quick Start](#quick-start)
- [Configuration Options](#configuration-options)
- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Advanced Configuration](#advanced-configuration)
- [Troubleshooting](#troubleshooting)

## Quick Start

```python
import finpack

# Use default configuration
finpack.configure_library()

# Or configure with custom settings
from finpack.shared.infrastructure.config import LibraryConfig, configure_library

config = LibraryConfig(
    log_level="INFO",
    log_to_console=True,
    enable_api_keys=True
)
configure_library(config)
```

## Configuration Options

### LibraryConfig Class

The `LibraryConfig` class provides comprehensive configuration options:

```python
@dataclass
class LibraryConfig:
    # Logging configuration
    log_level: str = "INFO"
    log_to_console: bool = True
    log_to_file: bool = False
    log_dir: Optional[str] = None

    # API configuration
    enable_api_keys: bool = True
    max_concurrent_requests: int = 5
    request_timeout: int = 30

    # Caching and performance
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour

    # Financial data settings
    yahoo_finance_rate_limit: int = 5
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
```

### Available Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_level` | str | "INFO" | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `log_to_console` | bool | True | Enable console logging |
| `log_to_file` | bool | False | Enable file logging |
| `log_dir` | str | None | Directory for log files |
| `enable_api_keys` | bool | True | Enable API key functionality |
| `max_concurrent_requests` | int | 5 | Maximum concurrent web requests |
| `request_timeout` | int | 30 | Request timeout in seconds |
| `cache_enabled` | bool | True | Enable caching |
| `cache_ttl` | int | 3600 | Cache time-to-live in seconds |
| `yahoo_finance_rate_limit` | int | 5 | Yahoo Finance API rate limit |
| `circuit_breaker_failure_threshold` | int | 5 | Circuit breaker failure threshold |
| `circuit_breaker_recovery_timeout` | int | 60 | Circuit breaker recovery timeout |

## Environment Variables

FinPack supports configuration via environment variables. These override the default values:

```bash
# Logging
export FINPACK_LOG_LEVEL=DEBUG
export FINPACK_LOG_TO_CONSOLE=true
export FINPACK_LOG_TO_FILE=true
export FINPACK_LOG_DIR=./logs

# API settings
export FINPACK_ENABLE_API_KEYS=true
export FINPACK_MAX_CONCURRENT_REQUESTS=10
export FINPACK_REQUEST_TIMEOUT=60

# Performance
export FINPACK_CACHE_ENABLED=true
export FINPACK_CACHE_TTL=7200

# Financial data
export FINPACK_YAHOO_FINANCE_RATE_LIMIT=10
export FINPACK_CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
export FINPACK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=120
```

### Loading Environment Variables

```python
import os
from finpack.shared.infrastructure.config import configure_library

# Set environment variables
os.environ['FINPACK_LOG_LEVEL'] = 'DEBUG'
os.environ['FINPACK_MAX_WORKERS'] = '10'

# Configure with environment variables
configure_library()
```

## Configuration Files

FinPack supports JSON configuration files:

```json
{
  "log_level": "DEBUG",
  "log_to_console": true,
  "log_to_file": true,
  "log_dir": "./logs",
  "enable_api_keys": true,
  "max_concurrent_requests": 10,
  "request_timeout": 60,
  "cache_enabled": true,
  "cache_ttl": 7200
}
```

### Using Configuration Files

```python
import os
from finpack.shared.infrastructure.config import configure_library

# Set config file path
os.environ['CONFIG_FILE'] = '/path/to/config.json'

# Configure from file
configure_library()
```

## Advanced Configuration

### Custom Logging Setup

```python
from finpack.shared.infrastructure.logging import LogManager

# Configure custom logging
log_manager = LogManager()
log_manager.configure(
    level="DEBUG",
    console=True,
    file=True,
    log_dir="./custom_logs",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
```

### Circuit Breaker Configuration

```python
from finpack.shared.infrastructure.utils import CircuitBreaker

# Create custom circuit breaker
breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=120,
    success_threshold=2
)
```

### API Key Management

```python
from finpack.shared.infrastructure.config.api_keys_config import APIKeysConfig

# Configure API keys
api_config = APIKeysConfig()
api_config.set_api_key('alpha_vantage', 'your_api_key_here')
api_config.set_api_key('iex_cloud', 'your_api_key_here')
```

## CLI Configuration

When using FinPack as a command-line tool, configuration is applied automatically:

```bash
# Use default configuration
python -m finpack fincli

# With environment variables
FINPACK_LOG_LEVEL=DEBUG python -m finpack fincli

# With config file
CONFIG_FILE=config.json python -m finpack fincli
```

## Troubleshooting

### Common Issues

1. **Configuration not applied**
   ```python
   # Ensure configure_library() is called
   import finpack
   finpack.configure_library()
   ```

2. **Logging not working**
   ```python
   # Check log level and console settings
   from finpack.shared.infrastructure.config import get_library_config
   config = get_library_config()
   print(f"Log level: {config.log_level}")
   print(f"Console logging: {config.log_to_console}")
   ```

3. **API rate limits**
   ```python
   # Adjust rate limiting
   config = LibraryConfig(
       yahoo_finance_rate_limit=2,  # Reduce requests
       request_timeout=60  # Increase timeout
   )
   configure_library(config)
   ```

4. **Cache not working**
   ```python
   # Enable and configure caching
   config = LibraryConfig(
       cache_enabled=True,
       cache_ttl=7200  # 2 hours
   )
   configure_library(config)
   ```

### Debug Configuration

```python
from finpack.shared.infrastructure.config import get_library_config

# Print current configuration
config = get_library_config()
print("Current configuration:")
for field in config.__dataclass_fields__:
    value = getattr(config, field)
    print(f"  {field}: {value}")
```

### Reset Configuration

```python
from finpack.shared.infrastructure.config import reset_library_config

# Reset to defaults
reset_library_config()
```

## Best Practices

1. **Use environment variables** for deployment-specific settings
2. **Keep sensitive data** (API keys) in environment variables
3. **Use configuration files** for complex setups
4. **Test configurations** in development before production
5. **Monitor logs** to verify configuration is applied correctly

## Migration from Legacy Configuration

If migrating from the old `fincli`/`fundainsight` setup:

```python
# Old way
from shared.infrastructure.config import get_config

# New way
from finpack.shared.infrastructure.config import get_library_config
import finpack

finpack.configure_library()
config = get_library_config()
```

For more information, see the [Migration Guide](MIGRATION_GUIDE.md).
