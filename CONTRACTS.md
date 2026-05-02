# CONTRACTS.md

This document defines all API contracts, message schemas, and service interfaces for Fin CLI.

## Table of Contents

1. [CLI Interfaces](#cli-interfaces)
2. [External API Contracts](#external-api-contracts)
3. [Internal Service Interfaces](#internal-service-interfaces)
4. [Data Schemas](#data-schemas)
5. [Configuration Schema](#configuration-schema)
6. [File Output Contracts](#file-output-contracts)

---

## CLI Interfaces

### fincli CLI

**Entry point:** `python -m fincli`

| Option | Alias | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--history` | `--hist` | flag | `False` | Reload filters from most recent search |
| `--debug` | - | flag | `False` | Enable DEBUG-level logging |

**Behavior:**
- With no options: launches interactive filter selection menu
- With `--history`: skips filter selection, loads from `fincli/local_history/filter_history.json`
- With `--debug`: sets logger level to `logging.DEBUG`

### fundainsight CLI

**Entry point:** `python -m fundainsight`

| Option | Alias | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--history` | `--hist` | flag | `False` | Reload filters from most recent search |
| `--debug` | - | flag | `False` | Enable DEBUG-level logging |
| `--set-filters` | - | string | `""` | JSON string of filter key-value pairs |
| `--scrape-link` | - | string | `""` | Direct Finviz URL with all filters pre-configured |

**Behavior:**
- Requires either `--history`, `--set-filters`, or `--scrape-link` to provide filter criteria
- Returns `None` and logs error if no filters are provided

---

## External API Contracts

### Finviz Stock Screener

**Endpoint:** `GET https://finviz.com/screener.ashx`

**Query Parameters:**

| Param | Type | Description | Example |
|-------|------|-------------|---------|
| `v` | int | View ID (always 111 for detailed) | `111` |
| `f` | string | Comma-separated filter codes | `fa_pe_u20,sec_energy` |
| `ft` | int | Filter type (always 2) | `2` |
| `r` | int | Row offset for pagination (1-indexed) | `1`, `21`, `41` |

**Filter Code Format:** `{category_key}_{value_code}`

Examples:
```
fa_pe_u20       -> P/E ratio under 20
sec_energy      -> Sector: Energy
cap_midover     -> Market cap: mid and over
ta_rsi14_ob70   -> RSI(14) overbought 70
```

**Response:** HTML page containing `<table class="styled-table-new">` with stock data rows.

**Pagination:**
- 20 rows per page
- Page count extracted from `.screener-pages` element
- Offset formula: `r = 20 * page_index + 1`

**Request Headers:**
```
User-Agent: [randomized from pool of Chrome/Firefox/Safari agents]
```

**Error Scenarios:**
- Cloudflare challenge → handled by cfscrape
- HTTP errors → raises `Exception("Http Error:", errh)`
- Timeout → 10 seconds per request

### Yahoo Finance (via yahooquery)

**Library:** `yahooquery.Ticker(symbol)`

**Methods Called:**

| Method | Parameters | Returns |
|--------|-----------|---------|
| `ticker.balance_sheet()` | `frequency='q'` | DataFrame (quarterly balance sheet) |
| `ticker.summary_detail` | - | dict `{symbol: {marketCap, ...}}` |
| `ticker.key_stats` | - | dict `{symbol: {sharesOutstanding, ...}}` |
| `ticker.history()` | `period="1mo"` | DataFrame with OHLCV columns |

**Balance Sheet Fields Used:**

| Field | Type | Description |
|-------|------|-------------|
| `TotalAssets` | float | Total assets |
| `CurrentAssets` | float | Total current assets |
| `OtherCurrentAssets` | float | Other current assets (subtracted) |
| `Goodwill` | float | Goodwill (subtracted from total) |
| `OtherNonCurrentAssets` | float | Other non-current assets (subtracted) |
| `StockholdersEquity` | float | Total stockholders equity |
| `Inventory` | float | Inventory (30% added back to current assets) |

**Summary Detail Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `marketCap` | float | Market capitalization |

**Key Stats Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `sharesOutstanding` | int | Total shares outstanding |

**History Data:**
- Period: 1 month
- Uses `close` column
- Aggregation: `.quantile(0.5)` (median as "average")

**Error Contract:**
- If any API call fails → returns `None` for the entire ticker
- Logged via `logger.error()`

---

## Internal Service Interfaces

### Stock Screening Service

**Module:** `fincli/app/main.py`

```python
def run_stock_screener(history: bool = False, debug: bool = False) -> None
```
- Orchestrates the full screening pipeline
- Saves result to CSV, no return value

```python
def fetch_urls(quarry: str, page_count: int) -> list[bytes]
```
- Fetches all paginated pages from Finviz
- Returns list of raw HTML content (bytes)

```python
def aggregate_rows(pages: list[bytes]) -> list[list]
```
- Parses all pages into row data
- Returns list of table data lists

```python
def build_data_frame(data_rows: list[list]) -> DataFrame
```
- Constructs final DataFrame with normalized columns
- Adds Symbol column, converts Market Cap, wraps Ticker in HYPERLINK

```python
def convert_market_cap_to_numeric(market_cap: str) -> float | str
```
- Converts "1.2B" -> 1200000000, "500M" -> 500000000, etc.
- Returns "N/A" for "_" or "-" values

### Fundamental Analysis Service

**Module:** `fundainsight/app/main.py`

```python
def get_opportunities(
    history: bool = False,
    debug: bool = False,
    set_filters: str = "",
    scrape_link: str = ""
) -> DataFrame | None
```
- Orchestrates the full analysis pipeline
- Returns filtered DataFrame or None

### Analysis Picker

**Module:** `fundainsight/app/picker.py`

```python
def picker(df: DataFrame | None) -> DataFrame | None
```
- Input: DataFrame with `Symbol` column from fincli screening
- Output: Filtered DataFrame with calculated ratios, or None
- Side effect: saves unfiltered CSV

```python
def add_new_columns(df: DataFrame) -> DataFrame
```
- Adds calculated columns: price_by_assets, price_by_current_assets, ratios

```python
def assign_old_df_to_new_df(old_df: DataFrame, new_df: DataFrame, column: str) -> DataFrame
```
- Copies column from screening results to financial data DataFrame
- Handles length mismatches (pads with NaN)

### Financial Calculator

**Module:** `fundainsight/calculators/equity_calc.py`

```python
def get_financial_data(ticker_name: str) -> dict | None
```
- Input: stock symbol string (e.g., "AAPL")
- Output: dict with financial metrics, or None on error
- Return schema:
  ```python
  {
      'Symbol': str,              # Ticker symbol
      'Market Cap': float,        # Market capitalization
      'Shares Outstanding': int,  # Total shares
      'Total Assets': float,      # Total assets (raw)
      'Adjusted Total Assets': float | None,       # After subtracting Goodwill, OtherNonCurrentAssets
      'Adjusted Total Current Assets': float | None, # After inventory adjustment
      'Total Equity': float,      # Stockholders equity
      'Average Price in Last 30 Days': float,  # Median close price, 1 month
  }
  ```

```python
def calculate_price_to_data(financial_data: dict, column_name: str) -> float
```
- Returns: `financial_data[column_name] / financial_data['Shares Outstanding']`

```python
def ratio_between_two_values(value1: float, value2: float) -> float
```
- Returns: `value1 / value2`, or `0` if value2 is 0

```python
def adjust_assets(
    balance_sheet: DataFrame,
    asset_type: str,
    adjustment_factor: float,
    additional_subtracts: list[str]
) -> float | None
```
- Subtracts specified items from asset value
- Adds `adjustment_factor * Inventory` if factor > 0
- Returns None if base asset field missing

### Filter Service

**Module:** `fundainsight/calculators/filters.py`

```python
class Filters:
    def __init__(self, df: DataFrame)
    def filter_country(self, country: str) -> Filters      # Exclude single country
    def filter_countries(self, countries: list) -> Filters   # Exclude multiple countries
    def filter_sector(self, sector: str) -> Filters          # Exclude sector
    def filter_price(self, column: str, price: float, less_than: bool = True) -> Filters
    def get_data(self) -> DataFrame                          # Return filtered DataFrame
```
- Fluent interface: all methods return `self` for chaining

### Configuration Builder

**Module:** `core/configuration/configurator.py`

```python
def build_config(use_history: bool = False, filters: str = "") -> Config
```
- If `use_history`: loads from `fundainsight/local_history/filter_history.json`
- If `filters`: parses JSON string to filter tuples

### Web Scraper

**Module:** `fincli/utils/web_scraper.py`

```python
def fetch_page_sync(url: str) -> bytes
```
- Returns raw HTML bytes
- Uses cfscrape for Cloudflare bypass
- 10-second timeout
- Randomized User-Agent header

### Query Builder

**Module:** `fincli/utils/quary_builders.py`

```python
def build_stock_screener_query(filters_tuple: tuple, v: int = 111, ft: int = 2) -> str
```
- Input: tuple of (filter_key, value_code) pairs
- Output: Full Finviz URL string

---

## Data Schemas

### Stock Screening DataFrame

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `No.` | str | Row number | "1" |
| `Ticker` | str | Excel HYPERLINK formula | `=HYPERLINK("https://finviz.com/...", "AAPL")` |
| `Company` | str | Company name | "Apple Inc." |
| `Sector` | str | Industry sector | "Technology" |
| `Industry` | str | Specific industry | "Consumer Electronics" |
| `Country` | str | Country of incorporation | "USA" |
| `Market Cap` | float | Normalized market cap | 2890000000000 |
| `P/E` | str | Price to earnings ratio | "28.52" |
| `Price` | str | Current stock price | "182.63" |
| `Change` | str | Daily price change | "-1.23%" |
| `Volume` | str | Daily trading volume | "52,436,789" |
| `Symbol` | str | Raw ticker symbol | "AAPL" |

### Fundamental Analysis DataFrame (Final)

| Column | Type | Description |
|--------|------|-------------|
| `Ticker` | str | Stock symbol |
| `Sector` | str | Industry sector |
| `Country` | str | Country |
| `Market Cap` | float | Market capitalization |
| `Average Price in Last 30 Days` | float | Median close price (1 month) |
| `price_by_assets` | float | Adjusted Total Assets / Shares Outstanding |
| `price_by_current_assets` | float | Adjusted Current Assets / Shares Outstanding |
| `price/price_to_current_assets_ratio` | float | Avg Price / price_by_current_assets |
| `price/price_to_assets_ratio` | float | Avg Price / price_by_assets |

### Financial Data Dict (Internal)

```python
{
    'Symbol': str,
    'Market Cap': float,
    'Shares Outstanding': int,
    'Total Assets': float,
    'Adjusted Total Assets': float | None,
    'Adjusted Total Current Assets': float | None,
    'Total Equity': float,
    'Average Price in Last 30 Days': float,
}
```

### Filter History JSON

**Location:** `fundainsight/local_history/filter_history.json` or `fincli/stock_screening/local_history/filter_history.json`

```json
{
  "filter_key": "value_code",
  "fa_pe": "u20",
  "sec": "energy"
}
```

---

## Configuration Schema

### Config (Pydantic Model)

```python
class Config(SystemSettings):
    name: str = "Stock Screener CLI config"
    description: str = "Configuration for the Stock Screener CLI app."
    use_history: bool = False
    filters: tuple = ()
    scrape_link: str = ""
```

### SystemSettings (Base)

```python
class SystemSettings(BaseModel):
    # Pydantic BaseModel base class
    # Supports .env file loading via SystemConfiguration
```

---

## File Output Contracts

### CSV Output Files

All files saved to `workspace_output/` with timestamp format `YYYY-MM-DD_HH-MM`.

| File Pattern | Module | Content |
|-------------|--------|---------|
| `stock_screener_{timestamp}.csv` | fincli | Screening results with hyperlinks |
| `funda_insight_result_unfiltered_{timestamp}.csv` | fundainsight | Pre-filter analysis data |
| `funda_insight_result_{timestamp}.csv` | fundainsight | Final filtered results |

### Log Files

| File | Location | Content |
|------|----------|---------|
| `activity.log` | `logs/` | All DEBUG+ log messages |
| `error.log` | `logs/` | ERROR level messages only |

**Activity Log Format:**
```
{timestamp} {level} {title} {message}
```

**Error Log Format:**
```
{timestamp} {level} {module}:{function}:{line} {title} {message}
```

---

## Filter Parameter Contracts

### Parameter Structure

Each filter parameter follows this schema:

```python
PARAM_NAME = ["query_key", {"value_code": "Display Name", ...}]
```

### Filter Categories

**Fundamental** (`fincli/resource/params/fundamental_params.py`):
- PE, FORWARD_PE, PEG, PS, PB, PC, PFCF
- EPS_GROWTH_THIS_YEAR, EPS_GROWTH_NEXT_YEAR, EPS_GROWTH_PAST_5, EPS_GROWTH_NEXT_5, EPS_GROWTH_QTR
- SALES_GROWTH_PAST_5, SALES_GROWTH_QTR
- ROA, ROE, ROI
- CURRENT_RATIO, QUICK_RATIO, LT_DEBT_EQUITY, DEBT_EQUITY, GROSS_MARGIN, OPERATING_MARGIN, NET_MARGIN, PAYOUT_RATIO
- INSIDER_OWN, INSIDER_TRANS, INST_OWN, INST_TRANS

**Descriptive** (`fincli/resource/params/descriptive_params.py`):
- EXCHANGE, INDEX, SECTOR, INDUSTRY, COUNTRY
- MARKET_CAP, DIVIDEND_YIELD, SHARES_OUTSTANDING
- ANALYST_RECOM, OPTION_SHORT, EARNINGS_DATE
- AVERAGE_VOLUME, CURRENT_VOLUME, PRICE, TARGET_PRICE, IPO_DATE

**Technical** (`fincli/resource/params/technical_params.py`):
- PERFORMANCE, VOLATILITY, RSI_14, GAP
- SMA_20, SMA_50, SMA_200
- CHANGE, CHANGE_FROM_OPEN
- HIGH_LOW_20D, HIGH_LOW_50D, HIGH_LOW_52W
- PATTERN, CANDLESTICK, BETA, ATR

### Hardcoded Analysis Filters

Applied in `fundainsight/app/picker.py`:
```python
.filter_countries(["Brazil", "Chile", "India", "Bermuda", "China"])
.filter_sector("Energy")
.filter_price("price/price_to_current_assets_ratio", 1)  # must be < 1
```
