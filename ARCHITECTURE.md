# ARCHITECTURE.md - Fin CLI System Architecture

This document is the source of truth for Fin CLI's system architecture.

## System Overview

**Fin CLI** is a two-mode Python command-line application that screens stocks from Finviz.com and runs price-to-asset fundamental analysis on the screening results using Yahoo Finance data. It is built as a library-style monorepo: each operating mode is its own importable package (`fincli`, `fundainsight`) with a Click entry point under `app/`. There is no server, no database, no network listener — outputs land as timestamped CSVs in `workspace_output/`.

```
                    +---------------------------+
                    |        End User           |
                    | (terminal / shell / CI)   |
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    |      Click CLI Layer      |
                    |  fincli/app/cli.py        |
                    |  fundainsight/app/cli.py  |
                    +-------------+-------------+
                                  |
                                  v
              +----------------------------------------+
              |          Orchestration Layer           |
              |  fincli/app/main.py                    |
              |  fundainsight/app/main.py + picker.py  |
              +-----+-------------------+--------------+
                    |                   |
        +-----------v--+              +-v--------------------+
        |   Screener   |              |   Fundamental        |
        |   pipeline   |              |   analysis pipeline  |
        | (HTML scrape)|              | (Yahoo enrichment)   |
        +------+-------+              +----------+-----------+
               |                                  |
               v                                  v
        +------+-------+                 +--------+--------+
        |  cfscrape    |                 |   yahooquery    |
        |  + BS4       |                 |   ThreadPool    |
        +------+-------+                 +--------+--------+
               |                                  |
        Finviz.com                       Yahoo Finance
        (Cloudflare-                     (balance sheet,
        protected HTML)                  market cap, prices)
```

## Module Map

| Module | Purpose | Key Files |
|---|---|---|
| `fincli/` | Stock screener — builds a Finviz query URL, fetches all paginated pages, parses the HTML stock table, writes CSV. | `fincli/app/cli.py`, `fincli/app/main.py`, `fincli/cli/cli_stock_screener.py`, `fincli/utils/web_scraper.py`, `fincli/utils/quary_builders.py`, `fincli/stock_screening/`, `fincli/resource/params/` |
| `fundainsight/` | Fundamental analysis — reuses the screener, enriches each ticker with Yahoo Finance balance-sheet + market-cap + price data, computes price-to-asset and price-to-current-asset ratios, applies country/sector/price filters. | `fundainsight/app/cli.py`, `fundainsight/app/main.py`, `fundainsight/app/picker.py`, `fundainsight/app/fincli.py`, `fundainsight/calculators/equity_calc.py`, `fundainsight/calculators/filters.py` |
| `core/` | Pure Python configuration framework — Pydantic base classes (`SystemSettings`), JSON-to-tuple conversion, Configurator builder. Has no external service dependencies. | `core/configuration/config_base.py`, `core/configuration/configurator.py`, `core/converters/json.py` |
| `config/` | Concrete `Config` instance for the application — extends `SystemSettings`, exposes `use_history`, `filters`, `scrape_link`, and `file_path(name)` for timestamped CSV destinations. | `config/config.py` |
| `logger/` | Singleton logger with three named handlers: a typing-effect console handler, plain console handler, and a JSON file handler. Imported as `from logger import logger`. | `logger/logger.py`, `logger/handlers/`, `logger/formatters/` |

Supporting (not part of the active runtime path):

| Module | Status |
|---|---|
| `scripts/` | Dependency-checking utilities. |
| `wisdom_fruit/` | Experimental, incomplete — do not depend on. |
| `shared/`, `example/`, `src/` | Empty scaffolding — slated for cleanup. |
| `tests/` | Folder layout exists (`tests/unit`, `tests/domain`, `tests/e2e`); test bodies will land in Phase 2 (see CLAUDE.md). |

## Data Flow

### Screening (`fincli`)

```
[1] Click CLI                       fincli/app/cli.py
       |   --history / --debug
       v
[2] Config build                    core/configuration/configurator.py
       |   loads filter_history.json when --history is set
       v
[3] Interactive filter selection    fincli/cli/cli_stock_screener.py
       |   user picks Fundamental / Descriptive / Technical filter values
       v
[4] Query URL construction          fincli/utils/quary_builders.py
       |   -> https://finviz.com/screener.ashx?v=111&f=<codes>&ft=2&r=<offset>
       v
[5] HTTP fetch (Cloudflare bypass)  fincli/utils/web_scraper.py
       |   cfscrape.create_scraper() with randomized User-Agent, 10s timeout
       v
[6] HTML table parsing              fincli/stock_screening/content.py
       |   BeautifulSoup over table.styled-table-new; reads page count,
       |   then iterates r=1, r=21, r=41, ... until exhausted
       v
[7] Row aggregation + DataFrame     fincli/app/main.py: aggregate_rows,
                                    build_data_frame
       |   normalizes Market Cap "1.2B" -> 1_200_000_000,
       |   wraps Ticker in =HYPERLINK() for Excel
       v
[8] CSV write                        Config.file_path("stock_screener")
       |   workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv
       v
       (done)
```

### Fundamental analysis (`fundainsight`)

```
[1] Click CLI                       fundainsight/app/cli.py
       |   --history / --debug / --set-filters / --scrape-link
       v
[2] get_opportunities()              fundainsight/app/main.py
       |
       v
[3] Reuse screener                   fundainsight/app/fincli.py
       |   calls into fincli to obtain a DataFrame of candidate symbols
       v
[4] picker(df)                       fundainsight/app/picker.py
       |
       +-> ThreadPoolExecutor parallel enrichment, one task per symbol:
       |       fundainsight/calculators/equity_calc.get_financial_data(ticker)
       |           -> yahooquery.Ticker(symbol).balance_sheet(frequency='q')
       |           -> .summary_detail        (market cap)
       |           -> .key_stats             (shares outstanding)
       |           -> .history(period='1mo') (30-day price; median = "average")
       |
       v
[5] add_new_columns(df)              fundainsight/app/picker.py
       |   price_by_assets             = Adjusted Total Assets / Shares Outstanding
       |   price_by_current_assets     = Adjusted Current Assets / Shares Outstanding
       |   price_to_assets_ratio       = Avg Price 30D / price_by_assets
       |   price_to_current_assets_ratio = Avg Price 30D / price_by_current_assets
       v
[6] Save unfiltered CSV              workspace_output/funda_insight_result_unfiltered_*.csv
       |
       v
[7] Filters chain                    fundainsight/calculators/filters.py
       |   .filter_countries([...])
       |   .filter_sector("Energy")
       |   .filter_price("price/price_to_current_assets_ratio", 1)   # < 1
       v
[8] Save final CSV                   workspace_output/funda_insight_result_*.csv
       v
       (done)
```

## Layering

```
+------------------------------------------------------------+
|                     Click CLI Layer                        |
|   fincli/app/cli.py            fundainsight/app/cli.py     |
|   (option parsing, --help text, logger level toggling)     |
+------------------------------------------------------------+
|                    Orchestration Layer                     |
|   fincli/app/main.py           fundainsight/app/main.py    |
|                                 fundainsight/app/picker.py |
|   (pipeline composition: build query -> fetch -> parse     |
|    -> DataFrame -> [enrich] -> filter -> write CSV)        |
+------------------------------------------------------------+
|                Domain / Calculators Layer                  |
|   fincli/cli/cli_stock_screener.py       (filter UI)       |
|   fundainsight/calculators/equity_calc.py (asset adj.)     |
|   fundainsight/calculators/filters.py     (DF filters)     |
+------------------------------------------------------------+
|                  Utility / I/O Layer                       |
|   fincli/utils/web_scraper.py       (HTTP via cfscrape)    |
|   fincli/utils/quary_builders.py    (URL construction)     |
|   fincli/stock_screening/           (BeautifulSoup parser) |
|   yahooquery (external library)     (Yahoo Finance API)    |
+------------------------------------------------------------+
|                  Cross-cutting                             |
|   config/config.py                                         |
|   core/configuration/                                      |
|   logger/                                                  |
+------------------------------------------------------------+
```

**Layering rule**: orchestration calls down into calculators and utility/I/O, never the reverse. Calculators (`equity_calc.py`, `filters.py`) receive already-fetched data (a pandas DataFrame, a yahooquery balance-sheet frame) and have no awareness of how the data was retrieved. Utility I/O layers know nothing about price-to-asset ratios.

There is no formal dependency-injection container. Wiring is done by direct import and function call in the orchestration layer. The Singleton logger is the only globally-visible runtime object.

## External Integrations

### Finviz.com (HTML scrape via cfscrape)

| Aspect | Detail |
|---|---|
| URL | `https://finviz.com/screener.ashx` |
| Method | `GET` with query parameters |
| Auth | None — Cloudflare protection bypassed by `cfscrape` |
| Anti-bot | Randomized User-Agent header per request |
| Pagination | 20 rows per page; `r=1`, `r=21`, `r=41`, ... offsets |
| Response | HTML, parsed via BeautifulSoup4 (`table.styled-table-new`) |
| Rate handling | Sequential requests; no explicit rate limiter |
| Timeout | 10 seconds per page fetch |
| Failure mode | Raised `Exception("Http Error:", err)` propagates up; logged |

### Yahoo Finance (via `yahooquery`)

| Aspect | Detail |
|---|---|
| Library | `yahooquery` (NOT `yfinance`) |
| Auth | None |
| Concurrency | `ThreadPoolExecutor` — one worker per ticker |
| Calls used | `Ticker(symbol).balance_sheet(frequency='q')`, `.summary_detail`, `.key_stats`, `.history(period='1mo')` |
| Failure mode | `equity_calc.get_financial_data()` returns `None` for the ticker on any exception or missing field; the row is filtered out of the result set |

## Folder Structure

```
algo_beta/
  fincli/                      # Stock screener
    app/
      cli.py                   # Click entry point
      main.py                  # Pipeline orchestrator
    cli/
      cli_stock_screener.py    # Interactive filter UI
    resource/
      params/
        fundamental_params.py
        descriptive_params.py
        technical_params.py
        const.py
    stock_screening/
      content.py               # HTML table extractor
      parsers.py               # row -> dict parser
      locators.py              # CSS / element locators
    utils/
      web_scraper.py           # cfscrape wrapper
      quary_builders.py        # Finviz URL construction
      user_agent_rotator.py
    local_history/             # filter_history.json (gitignored)

  fundainsight/                # Fundamental analysis
    app/
      cli.py                   # Click entry point
      main.py                  # get_opportunities() orchestrator
      picker.py                # ThreadPool enrichment + ratio calc
      fincli.py                # screener reuse adapter
    calculators/
      equity_calc.py           # asset adjustment + financial data fetch
      filters.py               # fluent DataFrame filter chain
    local_history/             # filter_history.json (gitignored)

  core/                        # Pure Python configuration framework
    configuration/
      config_base.py           # SystemSettings, Configurable[S]
      configurator.py          # build_config()
    converters/
      json.py                  # json_to_tuples()

  config/
    config.py                  # Concrete Config(SystemSettings)

  logger/                      # Singleton logger
    logger.py
    handlers/
    formatters/

  tests/                       # Phase 2 work — empty bodies today
    unit/
    domain/
    e2e/

  workspace_output/            # CSV results (gitignored)
  workspace_materials/         # Working notes (gitignored)
  logs/                        # activity.log + error.log (gitignored)

  docs/                        # Project documentation
    THESIS.md                  # Vision + roadmap (Phase 2 of harness work)
    MODULE_REFERENCE.md        # Per-module reference (Phase 2 of harness work)
    bugs/, refactoring/, reviewer/
    superpowers/specs/

  agents/                      # AI-agent rules + role files (Phase 2 of harness)
    rules/
    roles/

  .claude/                     # Claude Code harness configuration
    settings.json
    settings.local.json
    hooks/                     # SessionStart / PreToolUse / PostToolUse / Stop

  ARCHITECTURE.md              # this file
  CLAUDE.md
  CONTRACTS.md
  README.md
  TESTING.md
  TOOLS_REFERENCE.md
  AGENTS.md                    # (planned — Phase 6 of harness work)

  pyproject.toml
  requirements.txt
  run.sh / run.bat             # Convenience launchers
  singleton.py                 # Standalone metaclass utility
```

## Threading Model

- **Stock screening (`fincli`)** is fully synchronous. Pages from Finviz are fetched one at a time. This is intentional — the scraper cooperates with Finviz's anti-bot pacing by not flooding the host.
- **Fundamental analysis (`fundainsight`)** uses `concurrent.futures.ThreadPoolExecutor` in `picker.py` to parallelize Yahoo Finance lookups across symbols. Each task runs `equity_calc.get_financial_data(ticker)` independently. This is I/O-bound work (HTTPS + JSON parsing inside `yahooquery`), so the GIL is not the bottleneck.
- **Logger Singleton thread-safety**: the `Logger` Singleton is constructed once at import time. Its underlying `logging.Logger` handlers are Python's stdlib `logging` handlers, which are thread-safe by design. Concurrent `logger.info(...)` / `logger.error(...)` calls from the ThreadPool workers are safe. The typing-animation console handler serializes its writes to stdout under the same lock.
- **No `asyncio`** — all I/O is synchronous. Adding `aiohttp` or `httpx` is on the long-term roadmap (`docs/THESIS.md`) but not in active scope.

## Configuration Shape

```
core/configuration/config_base.py
    SystemConfiguration (Pydantic BaseSettings; .env file support)
    SystemSettings        (BaseModel; base for all app configs)
    Configurable[S]        (generic interface for "I produce a config of type S")

core/configuration/configurator.py
    build_config(use_history: bool = False, filters: str = "") -> Config
        - if use_history: read filter_history.json from local_history/
        - if filters:     parse JSON string -> tuple of (key, value) pairs
        - else:           empty Config (interactive selection will populate later)

config/config.py
    class Config(SystemSettings):
        name:        str  = "Stock Screener CLI config"
        description: str  = "Configuration for the Stock Screener CLI app."
        use_history: bool = False
        filters:     tuple = ()
        scrape_link: str  = ""

        def file_path(self, name: str) -> str:
            # Returns:  workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv
```

The configuration object is constructed once per CLI invocation and threaded through `main.py` -> calculators by direct argument passing. There is no global config singleton; the only global state is the logger.

When `--history` is set, the most recent filter selection is replayed verbatim — useful for re-running the same screen on a fresh trading day. The history file is plain JSON of `{filter_key: value_code}` pairs, written by the interactive filter UI on each successful run.

## Design Patterns

| Pattern | Where | Purpose |
|---|---|---|
| Singleton (metaclass) | `singleton.py` -> `logger/logger.py` | One process-wide logger instance |
| Builder | `core/configuration/configurator.build_config()` | Produce a `Config` from many possible sources (interactive, history, JSON, scrape link) |
| Fluent interface | `fundainsight/calculators/filters.Filters` | Chainable `.filter_country().filter_sector().filter_price()` calls |
| Strategy (data) | `fincli/resource/params/*.py` | Each filter category is a pluggable `[query_key, {value_code: display_name}]` dict |
| Template | `fincli/app/cli.py` and `fundainsight/app/cli.py` | Both modules follow an identical CLI -> orchestration -> domain layering, making the second module readable to anyone who has read the first |

## Performance & Resource Notes

- **Screening** is dominated by sequential HTTP latency (~0.5–2 s per Finviz page; Cloudflare adds variance).
- **Enrichment** parallelism is bounded by Yahoo Finance's tolerance — empirically the default `ThreadPoolExecutor` worker count works without observed throttling for typical screener result sizes (tens to a few hundred symbols).
- **Memory** stays modest: each enrichment task holds one balance-sheet DataFrame (a few KB). The combined unfiltered DataFrame written to CSV is the largest object in memory and is dominated by row count, not column complexity.
- **Failure mode for one ticker does not abort the run** — `get_financial_data` returns `None` for that symbol and `picker` filters Nones out before computing ratios.
