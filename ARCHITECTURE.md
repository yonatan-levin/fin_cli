# ARCHITECTURE.md

This document serves as the source of truth for Fin CLI's system architecture.

## System Overview

Fin CLI is a two-module financial analysis CLI that combines web-scraped stock screening data (Finviz.com) with fundamental financial data (Yahoo Finance) to identify undervalued stocks using price-to-asset ratio analysis.

```
+------------------+     +-------------------+     +------------------+
|   User (CLI)     | --> |    fincli          | --> |   CSV Output     |
|  Click interface |     |  Stock Screener    |     |  workspace_output|
+------------------+     +-------------------+     +------------------+
                                |
                                v
                         +-------------------+     +------------------+
                         |  fundainsight      | --> |   CSV Output     |
                         |  Analysis Engine   |     |  (3 files)       |
                         +-------------------+     +------------------+
```

## Module Architecture

### Layer Diagram

```
+-----------------------------------------------------------------+
|                        CLI Layer (Click)                         |
|   fincli/app/cli.py          fundainsight/app/cli.py            |
+-----------------------------------------------------------------+
|                     Application Layer                            |
|   fincli/app/main.py         fundainsight/app/main.py           |
|                              fundainsight/app/picker.py          |
|                              fundainsight/app/fincli.py          |
+-----------------------------------------------------------------+
|                      Domain / Business Logic                     |
|   fincli/cli/cli_stock_screener.py   (filter selection UI)      |
|   fundainsight/calculators/equity_calc.py  (financial calcs)    |
|   fundainsight/calculators/filters.py      (data filtering)     |
+-----------------------------------------------------------------+
|                     Infrastructure Layer                         |
|   fincli/utils/web_scraper.py        (HTTP + Cloudflare bypass) |
|   fincli/utils/quary_builders.py     (URL construction)         |
|   fincli/stock_screening/            (HTML parsing)             |
+-----------------------------------------------------------------+
|                     Cross-Cutting Concerns                       |
|   config/config.py + core/configuration/  (configuration)       |
|   logger/                                 (logging)             |
|   singleton.py                            (singleton metaclass) |
+-----------------------------------------------------------------+
```

### Module Dependency Graph

```
fundainsight
  |-- fundainsight.app.cli          (entry point)
  |-- fundainsight.app.main         (orchestration)
  |   |-- fundainsight.app.picker   (analysis pipeline)
  |   |   |-- fundainsight.calculators.equity_calc  (financial data + calcs)
  |   |   |-- fundainsight.calculators.filters      (DataFrame filtering)
  |   |-- fundainsight.app.fincli   (reuses fincli screening)
  |       |-- fincli.app.main       (stock screening)
  |-- config                        (configuration)
  |-- logger                        (logging)

fincli
  |-- fincli.app.cli                (entry point)
  |-- fincli.app.main               (orchestration)
  |   |-- fincli.cli.cli_stock_screener  (interactive filter UI)
  |   |-- fincli.stock_screening.content (HTML parsing)
  |   |-- fincli.stock_screening.parsers (row parsing)
  |   |-- fincli.utils.web_scraper       (HTTP fetching)
  |   |-- fincli.utils.quary_builders    (URL building)
  |-- fincli.resource.params        (filter definitions)
  |-- config                        (configuration)
  |-- logger                        (logging)
```

## Data Flow

### 1. Stock Screening Pipeline (fincli)

```
[User Input]
     |
     v
[cli.py] --history/--debug flags
     |
     v
[configurator.build_config()] --> loads filter_history.json if --history
     |
     v
[cli_stock_screener.select_filters_and_values()]
     |  Interactive: user picks filter categories (Fundamental/Descriptive/Technical)
     |  then picks specific filter values
     v
[quary_builders.build_stock_screener_query()]
     |  Constructs: https://finviz.com/screener.ashx?v=111&f=fa_pe_u20,sec_energy&ft=2
     v
[web_scraper.fetch_page_sync(url)]
     |  Uses cfscrape to bypass Cloudflare
     |  Randomized User-Agent headers
     v
[StockTableScreeningContent(html)]
     |  BeautifulSoup parses table.styled-table-new
     |  Extracts page_count for pagination
     v
[fetch_urls()] --> fetches all pages (r=1, r=21, r=41, ...)
     |
     v
[aggregate_rows()] --> combines all parsed rows
     |
     v
[build_data_frame()]
     |  Columns: No., Ticker, Company, Sector, Industry, Country,
     |           Market Cap, P/E, Price, Change, Volume
     |  Market Cap: "1.2B" -> 1200000000 (numeric)
     |  Ticker: wrapped in =HYPERLINK() for Excel
     v
[CSV saved to workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv]
```

### 2. Fundamental Analysis Pipeline (fundainsight)

```
[User Input]
     |
     v
[cli.py] --history/--debug/--set-filters/--scrape-link flags
     |
     v
[main.get_opportunities()]
     |
     v
[fincli.get_recommended_stocks()]  <-- Reuses fincli screening pipeline
     |  Returns DataFrame with Symbol column
     v
[picker.picker(df)]
     |
     +--> [ThreadPoolExecutor] parallelizes across all symbols:
     |         |
     |         v
     |    [equity_calc.get_financial_data(ticker)]
     |         |  yahooquery.Ticker(symbol)
     |         |  -> balance_sheet(frequency='q')    [quarterly]
     |         |  -> summary_detail                  [market cap]
     |         |  -> key_stats                       [shares outstanding]
     |         |  -> history(period="1mo")           [30-day price]
     |         |
     |         v
     |    Returns: {Symbol, Market Cap, Shares Outstanding,
     |              Total Assets, Adjusted Total Assets,
     |              Adjusted Total Current Assets, Total Equity,
     |              Average Price in Last 30 Days}
     |
     v
[add_new_columns(df)]
     |  price_by_assets = Adjusted Total Assets / Shares Outstanding
     |  price_by_current_assets = Adjusted Total Current Assets / Shares Outstanding
     |  price/price_to_current_assets_ratio = Avg Price 30D / price_by_current_assets
     |  price/price_to_assets_ratio = Avg Price 30D / price_by_assets
     v
[Save unfiltered CSV]
     |
     v
[Filters chain]
     |  .filter_countries(["Brazil", "Chile", "India", "Bermuda", "China"])
     |  .filter_sector("Energy")
     |  .filter_price("price/price_to_current_assets_ratio", 1)  # < 1 = undervalued
     v
[Save final CSV to workspace_output/funda_insight_result_YYYY-MM-DD_HH-MM.csv]
```

## External Service Integration

### Finviz.com

| Aspect | Detail |
|--------|--------|
| **Base URL** | `https://finviz.com/screener.ashx` |
| **Method** | GET with query parameters |
| **Auth** | Cloudflare protection (bypassed via cfscrape) |
| **Rate Limiting** | User-Agent rotation, sequential page fetches |
| **Query Format** | `?v=111&f={filter_codes}&ft=2&r={offset}` |
| **Pagination** | 20 rows per page, offset: r=1, r=21, r=41... |
| **Response** | HTML table (`table.styled-table-new`) |

### Yahoo Finance (yahooquery)

| Aspect | Detail |
|--------|--------|
| **Library** | `yahooquery` (not `yfinance`) |
| **Auth** | No API key required |
| **Concurrency** | ThreadPoolExecutor (one thread per ticker) |
| **Data Points** | `balance_sheet(frequency='q')`, `summary_detail`, `key_stats`, `history(period="1mo")` |
| **Error Handling** | Returns `None` on failure, filtered from results |

## Configuration System

```
config/config.py (Config class)
     ^
     |
core/configuration/config_base.py
  |-- SystemConfiguration (Pydantic BaseModel, .env support)
  |-- SystemSettings (base for all settings)
  |-- Configurable[S] (generic interface)
     ^
     |
core/configuration/configurator.py
  |-- build_config(use_history, filters)
  |   Loads from filter_history.json when history=True
  |   Parses filter strings via json_to_tuples()
```

**Config Properties:**
- `use_history: bool` - Load saved filter history
- `filters: tuple` - Parsed filter tuples `[(key, value), ...]`
- `scrape_link: str` - Direct Finviz URL override
- `file_path(name)` - Generates timestamped CSV path

## Logging Architecture

```
Logger (Singleton metaclass)
  |
  |-- typing_logger (TYPER)
  |     |-- TypingConsoleHandler (simulated typing, INFO+)
  |     |-- FileHandler (activity.log, DEBUG+)
  |     |-- FileHandler (error.log, ERROR+)
  |
  |-- logger (LOGGER)  <-- Primary logger used throughout
  |     |-- ConsoleHandler (simple print, DEBUG+)
  |     |-- FileHandler (activity.log, DEBUG+)
  |     |-- FileHandler (error.log, ERROR+)
  |
  |-- json_logger (JSON_LOGGER)
        |-- FileHandler (activity.log, DEBUG+)
        |-- FileHandler (error.log, ERROR+)
        |-- JsonFileHandler (dynamic, per-call)

Formatters:
  - AlgoFormatter: colored title + plain message
  - JsonFormatter: pass-through for JSON data
```

## File System Layout

```
workspace_output/           # All CSV output (gitignored)
logs/                       # activity.log, error.log (gitignored)
fincli/local_history/       # Saved fincli filter history (gitignored)
fundainsight/local_history/ # Saved fundainsight filter history (gitignored)
```

## Design Patterns

| Pattern | Where Used | Purpose |
|---------|-----------|---------|
| **Singleton** | `Logger`, via `singleton.py` metaclass | One logger instance per process |
| **Builder** | `configurator.build_config()` | Construct Config from multiple sources |
| **Fluent Interface** | `Filters` class chain | Readable filter composition: `.filter_x().filter_y().get_data()` |
| **Strategy** | Filter parameter dicts | Each parameter category is a pluggable dict |
| **Template** | `cli.py` -> `main.py` pattern | Both modules follow identical CLI-to-orchestration structure |

## Concurrency Model

- **Stock screening** (`fincli`): Sequential HTTP requests (one page at a time)
- **Financial data** (`fundainsight`): Parallel via `ThreadPoolExecutor` (one thread per ticker symbol)
- **No async**: All I/O is synchronous (requests + cfscrape)

## Security Considerations

- `.env` file support exists but is currently empty
- Finviz scraping uses randomized User-Agents to avoid blocking
- No API keys stored in code (Yahoo Finance doesn't require one)
- `workspace_output/` and filter history are gitignored
- No authentication/authorization (CLI tool, no server)
