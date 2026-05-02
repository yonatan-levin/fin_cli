# CLAUDE.md - Fin CLI Project Guide

## Project Overview

**Fin CLI** is a Python command-line tool for financial stock analysis. It screens stocks from Finviz.com and performs fundamental analysis using Yahoo Finance data to identify undervalued stocks based on price-to-asset ratios.

## Quick Reference

```bash
# Run the app
python -m fincli          # Stock screening mode
python -m fundainsight    # Fundamental analysis mode

# Or use entry scripts
./run.sh                  # Linux/macOS
run.bat                   # Windows

# Run tests
pytest tests/

# Install dependencies
pip install -r requirements.txt
```

## Architecture

Two main modules:
- **`fincli/`** - Stock screener: fetches and parses Finviz.com stock tables
- **`fundainsight/`** - Fundamental analysis: enriches screened stocks with Yahoo Finance data, calculates price-to-asset ratios, filters for undervalued opportunities

Supporting modules:
- **`config/`** - Pydantic-based configuration with history support
- **`core/`** - Base configuration classes and JSON converters
- **`logger/`** - Singleton logger with console (typing effect), file, and JSON handlers
- **`scripts/`** - Dependency checking utilities

## Key Data Flow

```
User selects Finviz filters (CLI)
  -> Query URL built -> HTML fetched (cfscrape) -> Table parsed (BeautifulSoup)
  -> DataFrame created -> [fundainsight only: Yahoo Finance enrichment via ThreadPoolExecutor]
  -> Ratios calculated -> Filters applied -> CSV saved to workspace_output/
```

## Tech Stack

- **Python 3.12+**
- **Click** - CLI framework
- **pandas** - Data manipulation
- **yahooquery** - Yahoo Finance API (NOT yfinance)
- **cfscrape** - Cloudflare bypass for Finviz scraping
- **BeautifulSoup4** - HTML parsing (via cfscrape)
- **Pydantic** - Configuration validation
- **colorama** - Terminal colors

## Code Conventions

- Modules follow `app/cli.py` -> `app/main.py` -> domain logic pattern
- Configuration uses Pydantic `BaseModel` with `SystemSettings` base class
- Logger is a Singleton (metaclass-based) - import via `from logger import logger`
- Filter parameters defined as lists: `[query_key, {value_code: display_name}]`
- CSV output uses timestamped filenames: `{name}_{YYYY-MM-DD_HH-MM}.csv`
- Financial data fetched in parallel using `ThreadPoolExecutor`

## Important Files

| File | Purpose |
|------|---------|
| `fincli/app/main.py` | Stock screening orchestration |
| `fundainsight/app/picker.py` | Fundamental analysis pipeline |
| `fundainsight/calculators/equity_calc.py` | Financial calculations (price-to-asset ratios) |
| `fundainsight/calculators/filters.py` | DataFrame filtering (country, sector, price) |
| `fincli/utils/web_scraper.py` | HTTP fetching with Cloudflare bypass |
| `fincli/utils/quary_builders.py` | Finviz URL query construction |
| `fincli/resource/params/` | All Finviz filter parameter definitions |
| `config/config.py` | Main Config class |
| `core/configuration/configurator.py` | Config builder |
| `logger/logger.py` | Singleton Logger class |

## External Services

1. **Finviz.com** (`https://finviz.com/screener.ashx`) - Stock screening data
2. **Yahoo Finance** (via `yahooquery`) - Balance sheets, market cap, price history

## Output

All results saved to `workspace_output/` as CSV:
- `stock_screener_*.csv` - Screening results with Excel hyperlinks
- `funda_insight_result_unfiltered_*.csv` - Pre-filter analysis
- `funda_insight_result_*.csv` - Final filtered results

## Known Issues / Tech Debt

- `pyproject.toml` lists `yfinance` but code uses `yahooquery` - needs sync
- Test `.py` files are missing (only `__pycache__` remains) - tests need recreation
- `wisdom_fruit/` module is experimental/incomplete
- `shared/`, `example/`, `src/finpack/` directories are empty scaffolding
- Some hardcoded values in `picker.py` (excluded countries, sectors) should be configurable
- `not int` checks in `equity_calc.py:adjust_assets()` are always True (bug - `int` is truthy)
