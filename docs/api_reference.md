# FinPack API Reference

This document provides a reference for the unified FinPack API (library-first, no CLI required).

## Quick Start
```python
from finpack import StockScreener, FundamentalAnalyzer

# Screen using a Finviz link
screener = StockScreener()
df = screener.screen(scrape_link="https://finviz.com/screener.ashx?v=111&f=cap_large")

# Compute simple ratios via Yahoo
analyzer = FundamentalAnalyzer()
ratios = analyzer.ratios("AAPL")
```

## Package Structure (src layout)
```
src/finpack/
├── core/
│   ├── screener.py         # StockScreener facade
│   └── analyzer.py         # FundamentalAnalyzer facade
├── providers/              # Provider adapters (yahooquery)
├── models/                 # Finviz parsing models
└── utils/                  # Logging, query builders, scraper
```

## Table of Contents

- [Package Structure](#package-structure)
- [Core Functions](#core-functions)
- [Stock Screening API](#stock-screening-api)
- [Fundamental Analysis API](#fundamental-analysis-api)
- [Configuration API](#configuration-api)
- [Data Types](#data-types)

## Package Structure

```
finpack/
├── __init__.py              # Main package initialization
├── __main__.py              # CLI entry point
├── fincli/                  # Stock screening module
│   ├── __init__.py
│   ├── __main__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py          # Stock screening functions
│       └── cli.py           # CLI commands
├── fundainsight/            # Fundamental analysis module
│   ├── __init__.py
│   ├── __main__.py
│   └── app/
│       ├── __init__.py
│       ├── main.py          # Analysis functions
│       └── stock_picker.py  # Stock picking algorithms
└── shared/                  # Shared infrastructure
    ├── __init__.py
    └── infrastructure/
        ├── config/          # Configuration management
        ├── logging/         # Logging utilities
        └── utils/           # Utility functions
```

## Core Functions

### finpack.configure_library(config=None)

Configure the FinPack library with the specified configuration.

**Parameters:**
- `config` (LibraryConfig, optional): Configuration object. If None, uses defaults.

**Returns:** None

**Example:**
```python
import finpack
from finpack.shared.infrastructure.config import LibraryConfig

config = LibraryConfig(log_level="DEBUG")
finpack.configure_library(config)
```

### finpack.reset_library_config()

Reset the library configuration to defaults.

**Returns:** None

**Example:**
```python
import finpack
finpack.reset_library_config()
```

## Stock Screening API

### finpack.fincli.app.main.run_stock_screener(history=False, debug=False)

Run the stock screening process.

**Parameters:**
- `history` (bool): Whether to use history filters
- `debug` (bool): Enable debug mode

**Returns:** None

**Example:**
```python
from finpack.fincli.app.main import run_stock_screener
run_stock_screener(history=True, debug=False)
```

### finpack.fincli.app.main.fetch_urls(base_url, max_pages=0)

Fetch URLs for stock screening.

**Parameters:**
- `base_url` (str): Base URL for screening
- `max_pages` (int): Maximum pages to fetch (0 for unlimited)

**Returns:** List[str] - List of fetched URLs

**Example:**
```python
from finpack.fincli.app.main import fetch_urls
urls = fetch_urls("https://finviz.com/", max_pages=5)
```

### finpack.fincli.app.main.aggregate_rows(pages)

Aggregate stock data from fetched pages.

**Parameters:**
- `pages` (List[str]): List of HTML page content

**Returns:** List[List[Dict]] - Aggregated stock data

**Example:**
```python
from finpack.fincli.app.main import aggregate_rows
rows = aggregate_rows(pages)
```

### finpack.fincli.app.main.build_data_frame(data_rows)

Build pandas DataFrame from stock data.

**Parameters:**
- `data_rows` (List[List[Dict]]): Stock data rows

**Returns:** pandas.DataFrame - Processed stock data

**Example:**
```python
from finpack.fincli.app.main import build_data_frame
df = build_data_frame(rows)
```

## Fundamental Analysis API

### finpack.fundainsight.app.main.get_opportunities()

Get fundamental analysis opportunities.

**Returns:** Dict - Analysis results

**Example:**
```python
from finpack.fundainsight.app.main import get_opportunities
results = get_opportunities()
```

### finpack.fundainsight.app.stock_picker.StockPicker

Main class for stock picking analysis.

#### Methods:

**`__init__(self)`**
Initialize the stock picker.

**`find_opportunities(self, symbols)`**
Find investment opportunities for given symbols.

**Parameters:**
- `symbols` (List[str]): List of stock symbols

**Returns:** List[Dict] - Opportunity analysis results

**Example:**
```python
from finpack.fundainsight.app.stock_picker import StockPicker

picker = StockPicker()
opportunities = picker.find_opportunities(['AAPL', 'MSFT'])
```

## Configuration API

### finpack.shared.infrastructure.config.LibraryConfig

Configuration dataclass for the library.

**Attributes:**
- `log_level` (str): Logging level
- `log_to_console` (bool): Enable console logging
- `log_to_file` (bool): Enable file logging
- `log_dir` (Optional[str]): Log directory
- `enable_api_keys` (bool): Enable API key functionality
- `max_concurrent_requests` (int): Max concurrent requests
- `request_timeout` (int): Request timeout in seconds
- `cache_enabled` (bool): Enable caching
- `cache_ttl` (int): Cache time-to-live
- `yahoo_finance_rate_limit` (int): Yahoo Finance rate limit
- `circuit_breaker_failure_threshold` (int): Circuit breaker threshold
- `circuit_breaker_recovery_timeout` (int): Circuit breaker recovery timeout

**Example:**
```python
from finpack.shared.infrastructure.config import LibraryConfig

config = LibraryConfig(
    log_level="DEBUG",
    max_concurrent_requests=10
)
```

### finpack.shared.infrastructure.config.configure_library(config)

Configure the library with the given configuration.

**Parameters:**
- `config` (LibraryConfig): Configuration object

**Returns:** None

### finpack.shared.infrastructure.config.get_library_config()

Get the current library configuration.

**Returns:** LibraryConfig - Current configuration

**Example:**
```python
from finpack.shared.infrastructure.config import get_library_config
config = get_library_config()
print(f"Log level: {config.log_level}")
```

### finpack.shared.infrastructure.config.reset_library_config()

Reset library configuration to defaults.

**Returns:** None

### finpack.shared.infrastructure.config.is_library_configured()

Check if the library is configured.

**Returns:** bool - True if configured

## Data Types

### StockData

Dictionary containing stock information:

```python
{
    "No.": "1",
    "Ticker": "AAPL",
    "Company": "Apple Inc",
    "Sector": "Technology",
    "Industry": "Consumer Electronics",
    "Country": "USA",
    "Market Cap": "2.5T",
    "P/E": "25.5",
    "Price": "150.00",
    "Change": "+2.5",
    "Volume": "1000000",
    "Link": "http://example.com"
}
```

### FinancialData

Dictionary containing financial metrics:

```python
{
    "symbol": "AAPL",
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "market_cap": 2000000000000,
    "shares_outstanding": 15000000000,
    "average_price_30d": 180.0,
    "balance_sheet": {
        "total_assets": 300000000000,
        "current_assets": 100000000000,
        "inventory": 5000000000,
        "goodwill": 10000000000,
        "other_current_assets": 2000000000,
        "other_non_current_assets": 5000000000,
        "total_liabilities": 150000000000,
        "stockholders_equity": 150000000000
    }
}
```

### OpportunityScore

Dictionary containing opportunity analysis:

```python
{
    "symbol": "AAPL",
    "score": 85.5,
    "recommendation": "BUY",
    "metrics": {
        "price_to_assets_ratio": 0.5,
        "price_to_current_assets_ratio": 1.2,
        "adjusted_total_assets": 300000000000,
        "adjusted_current_assets": 100000000000
    }
}
```

## Error Types

### finpack.shared.infrastructure.config.InvalidTickerError

Raised when an invalid ticker symbol is provided.

**Example:**
```python
from finpack.shared.infrastructure.config import InvalidTickerError

try:
    # Some operation
    pass
except InvalidTickerError as e:
    print(f"Invalid ticker: {e}")
```

### finpack.shared.domain.services.DataRetrievalError

Raised when data retrieval fails.

**Example:**
```python
from finpack.shared.domain.services import DataRetrievalError

try:
    # Data retrieval operation
    pass
except DataRetrievalError as e:
    print(f"Data retrieval failed: {e}")
```

## Utility Functions

### finpack.shared.infrastructure.utils.measure_time(func)

Decorator to measure function execution time.

**Parameters:**
- `func` (Callable): Function to measure

**Returns:** Callable - Wrapped function

**Example:**
```python
from finpack.shared.infrastructure.utils import measure_time

@measure_time
def slow_operation():
    import time
    time.sleep(1)
    return "Done"

result = slow_operation()
# Output: slow_operation took 1.001 seconds
```

### finpack.shared.infrastructure.logging.LogManager

Logging utility class.

**Methods:**
- `configure(level, console, file, log_dir)`: Configure logging
- `get_logger(name)`: Get a logger instance

**Example:**
```python
from finpack.shared.infrastructure.logging import LogManager

log_manager = LogManager()
log_manager.configure(level="DEBUG", console=True, file=True)

logger = log_manager.get_logger("my_module")
logger.info("This is an info message")
```

## CLI Commands

### finpack fincli

Run the stock screening CLI.

**Options:**
- `--help`: Show help message

**Example:**
```bash
python -m finpack fincli
```

### finpack fundainsight

Run the fundamental analysis CLI.

**Options:**
- `--help`: Show help message

**Example:**
```bash
python -m finpack fundainsight
```

### finpack --version

Show the version information.

**Example:**
```bash
python -m finpack --version
```

## Migration Notes

### From fincli

```python
# Old
from fincli.app.main import run_stock_screener

# New
from finpack.fincli.app.main import run_stock_screener
import finpack
finpack.configure_library()
```

### From fundainsight

```python
# Old
from fundainsight.app.main import get_opportunities

# New
from finpack.fundainsight.app.main import get_opportunities
import finpack
finpack.configure_library()
```

### From shared

```python
# Old
from shared.infrastructure.config import get_config

# New
from finpack.shared.infrastructure.config import get_library_config
import finpack
finpack.configure_library()
```

For more detailed migration information, see the [Migration Guide](MIGRATION_GUIDE.md).
