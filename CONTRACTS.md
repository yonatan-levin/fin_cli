# CONTRACTS.md - Fin CLI Contracts

This document defines the **stable surfaces** that other code (downstream automation, Phase 2 tests, future modules) and end users rely on. A contract here is a promise: changing it is a breaking change, governed by the stability policy at the bottom of this file.

algo_beta has **no REST API, no HTTP listener, no broker integration, no database**. It is a CLI plus a set of importable Python packages, plus the CSVs it writes. The contracts therefore live in five places:

1. The **CLI command surface** — every Click command, every option, every exit code.
2. The **Finviz query parameter contract** — the `[query_key, {value_code: display_name}]` filter shape under `fincli/resource/params/`.
3. The **Yahoo Finance data shape contract** — the fields read from `yahooquery.Ticker` and the failure modes when fields are missing.
4. The **CSV output schema** — column names, dtypes, sort order, file naming.
5. The **Configuration JSON shape** — the Pydantic-validated `Config` produced by `core/configuration/configurator.py`.

A sixth surface is the **logger contract** — what `from logger import logger` returns and what its methods promise.

---

## 1. CLI Command Surface

### 1.1 `fincli` — stock screener

**Entry point:** `python -m fincli` (resolves to `fincli/app/cli.py:run_main`).

```
Usage: python -m fincli [OPTIONS]

  Welcome to the Stock Screener CLI!
```

| Option | Alias | Type | Default | Description |
|---|---|---|---|---|
| `--history` | `--hist` | flag | `False` | Reload the most recent filter selection from `fincli/local_history/filter_history.json` instead of prompting interactively. |
| `--debug` | — | flag | `False` | Set the logger level to `DEBUG`. |

**Behavior**

| State | What happens |
|---|---|
| No subcommand, no `--history` | Interactive filter-selection menu (Fundamental / Descriptive / Technical), then full screener pipeline, then CSV write. |
| `--history` | Skip the interactive menu; reuse the last filter set. |
| `--debug` | Logger level lowered to `DEBUG` for the duration of the run. |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | Run completed; CSV written. |
| non-zero | Unhandled exception bubbled to the Click runner. The traceback is printed to stderr and written to `logs/error.log`. |

**Output side effects**

- `workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv`
- `fincli/local_history/filter_history.json` is overwritten with the current filter selection on a successful run.
- `logs/activity.log` (DEBUG+) and `logs/error.log` (ERROR+) appended.

### 1.2 `fundainsight` — fundamental analysis

**Entry point:** `python -m fundainsight` (resolves to `fundainsight/app/cli.py:run_main`).

```
Usage: python -m fundainsight [OPTIONS]
```

| Option | Alias | Type | Default | Description |
|---|---|---|---|---|
| `--history` | `--hist` | flag | `False` | Reload the most recent filter selection from `fundainsight/local_history/filter_history.json`. |
| `--debug` | — | flag | `False` | Set logger level to `DEBUG`. |
| `--set-filters` | — | string | `""` | JSON string of `{filter_key: value_code}` pairs. Parsed by `core/converters/json.py:json_to_tuples`. |
| `--scrape-link` | — | string | `""` | A direct Finviz screener URL. Bypasses both interactive selection and history. |

**Behavior**

The mode requires a filter source. Provide exactly one of `--history`, `--set-filters`, or `--scrape-link`. With none of them, `get_opportunities` logs an error and returns `None` — no CSV is written.

| State | What happens |
|---|---|
| `--history` | Reuse last filter set. |
| `--set-filters '<json>'` | Parse the JSON, build the screener URL from the implied filters. |
| `--scrape-link '<url>'` | Use the URL verbatim; do not rebuild it. |
| None of the above | Log error, return `None`. |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | Run completed (CSV written, *or* a controlled `None` return logged). |
| non-zero | Unhandled exception. |

**Output side effects**

- `workspace_output/funda_insight_result_unfiltered_YYYY-MM-DD_HH-MM.csv` (always, when enrichment succeeds for at least one ticker)
- `workspace_output/funda_insight_result_YYYY-MM-DD_HH-MM.csv` (after the country / sector / price filter chain)
- `fundainsight/local_history/filter_history.json` is overwritten on success.

### 1.3 Convenience launchers

| File | Behavior |
|---|---|
| `run.sh` | Linux / macOS Bash launcher; presents a menu to choose between `fincli` and `fundainsight`. |
| `run.bat` | Windows batch equivalent. |

These call `python -m <mode>` under the hood. They are not contractually distinct from the `python -m` invocations.

---

## 2. Finviz Query Parameter Contract

Each Finviz filter is declared as a **two-element list**:

```python
PARAM_NAME = ["<query_key>", {"<value_code>": "<Display Name>", ...}]
```

- The first element is the Finviz URL query-key fragment (e.g., `"fa_pe"`, `"sec"`, `"ta_rsi14"`).
- The second element is a dict mapping the URL value-code (e.g., `"u20"`, `"energy"`) to a human-readable label shown in the interactive UI.
- The full filter code submitted to Finviz is `f"{query_key}_{value_code}"`. Multiple filters concatenate with commas: `f=fa_pe_u20,sec_energy,ta_rsi14_ob70`.

Adding a new filter parameter is contract-stable as long as you keep the two-element list shape. Renaming an existing key, value-code, or display name is breaking — downstream history files (`filter_history.json`) reference these by name.

### 2.1 Parameter files

| File | Semantic group | Examples |
|---|---|---|
| `fincli/resource/params/fundamental_params.py` | Fundamental ratios and growth | `PE`, `FORWARD_PE`, `PEG`, `PS`, `PB`, `PC`, `PFCF`, `EPS_GROWTH_THIS_YEAR`, `EPS_GROWTH_NEXT_YEAR`, `EPS_GROWTH_PAST_5`, `EPS_GROWTH_NEXT_5`, `EPS_GROWTH_QTR`, `SALES_GROWTH_PAST_5`, `SALES_GROWTH_QTR`, `ROA`, `ROE`, `ROI`, `CURRENT_RATIO`, `QUICK_RATIO`, `LT_DEBT_EQUITY`, `DEBT_EQUITY`, `GROSS_MARGIN`, `OPERATING_MARGIN`, `NET_MARGIN`, `PAYOUT_RATIO`, `INSIDER_OWN`, `INSIDER_TRANS`, `INST_OWN`, `INST_TRANS` |
| `fincli/resource/params/descriptive_params.py` | Descriptive / classification | `EXCHANGE`, `INDEX`, `SECTOR`, `INDUSTRY`, `COUNTRY`, `MARKET_CAP`, `DIVIDEND_YIELD`, `SHARES_OUTSTANDING`, `ANALYST_RECOM`, `OPTION_SHORT`, `EARNINGS_DATE`, `AVERAGE_VOLUME`, `CURRENT_VOLUME`, `PRICE`, `TARGET_PRICE`, `IPO_DATE` |
| `fincli/resource/params/technical_params.py` | Price, momentum, technical | `PERFORMANCE`, `VOLATILITY`, `RSI_14`, `GAP`, `SMA_20`, `SMA_50`, `SMA_200`, `CHANGE`, `CHANGE_FROM_OPEN`, `HIGH_LOW_20D`, `HIGH_LOW_50D`, `HIGH_LOW_52W`, `PATTERN`, `CANDLESTICK`, `BETA`, `ATR` |
| `fincli/resource/params/const.py` | Static constants used by the interactive UI (category names, sentinel values) |

### 2.2 URL contract

```
https://finviz.com/screener.ashx?v=111&f=<filter_codes>&ft=2&r=<offset>
```

| Parameter | Type | Notes |
|---|---|---|
| `v` | int | View identifier. **Always `111`** (full-detail view). |
| `f` | string | Comma-separated filter codes. |
| `ft` | int | Filter type. **Always `2`**. |
| `r` | int | 1-indexed row offset for pagination. Page boundaries are `1, 21, 41, ...`. |

Headers: a randomized User-Agent from `fincli/utils/user_agent_rotator.py`.

Failure shape: `cfscrape` raises an exception on HTTP errors; the screener wraps it as `Exception("Http Error:", err)` and lets it propagate.

---

## 3. Yahoo Finance Data Shape Contract

`fundainsight/calculators/equity_calc.py:get_financial_data(ticker)` is the single Yahoo-facing function. It calls `yahooquery.Ticker(symbol)` and reads four shapes:

### 3.1 Balance sheet — `Ticker(symbol).balance_sheet(frequency='q')`

Returns a pandas `DataFrame`. Fields read by `equity_calc`:

| Field | Read by | Notes |
|---|---|---|
| `TotalAssets` | `get_financial_data` (raw) and `adjust_assets` | Required |
| `CurrentAssets` | `adjust_assets("CurrentAssets", 0.3, ["OtherCurrentAssets"])` | Required |
| `OtherCurrentAssets` | Subtracted by `adjust_assets` | Optional — if missing, treated as 0 (caught `KeyError`) |
| `Goodwill` | Subtracted by `adjust_assets` for `TotalAssets` | Optional |
| `OtherNonCurrentAssets` | Subtracted by `adjust_assets` for `TotalAssets` | Optional |
| `Inventory` | 30% added back by `adjust_assets` for `CurrentAssets` | Optional |
| `StockholdersEquity` | Read directly | Required |

If any required field is missing, `get_financial_data` returns `None`.

### 3.2 Summary detail — `Ticker(symbol).summary_detail`

Dict-of-dicts: `{symbol: {field: value, ...}}`. Field read:

| Field | Type | Notes |
|---|---|---|
| `marketCap` | float | Required |

### 3.3 Key stats — `Ticker(symbol).key_stats`

Dict-of-dicts: `{symbol: {field: value, ...}}`. Field read:

| Field | Type | Notes |
|---|---|---|
| `sharesOutstanding` | int | Required |

### 3.4 Price history — `Ticker(symbol).history(period='1mo')`

Returns a pandas `DataFrame` with OHLCV columns. The function reads:

| Column | Aggregation | Notes |
|---|---|---|
| `close` | `.quantile(0.5)` (median = "average price in last 30 days") | Required |

### 3.5 Failure mode

If any of these calls raises an exception, returns `None`, or yields a missing-field `KeyError` on a *required* field, `get_financial_data` returns `None` for the entire ticker. The error is logged to the Singleton logger. Downstream `picker.py` filters out `None` rows before computing ratios — so a single bad ticker does not abort the run.

This is the entire promise. There is no retry, no circuit breaker, no backoff. Adding any is a contract change (and probably belongs in Phase 2 alongside tests).

---

## 4. CSV Output Schema

All CSV output lands in `workspace_output/`. File names follow the pattern produced by `Config.file_path(name)`:

```
workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv
```

The minute-level timestamp lets multiple runs in a single hour coexist without collision.

### 4.1 `stock_screener_*.csv`

Produced by `fincli/app/main.py:build_data_frame`.

| Column | dtype | Description | Example |
|---|---|---|---|
| `No.` | str | Row number from the Finviz table | `"1"` |
| `Ticker` | str | Excel `=HYPERLINK(...)` formula wrapping the symbol | `=HYPERLINK("https://finviz.com/quote.ashx?t=AAPL", "AAPL")` |
| `Company` | str | Company name | `"Apple Inc."` |
| `Sector` | str | Industry sector | `"Technology"` |
| `Industry` | str | Specific industry | `"Consumer Electronics"` |
| `Country` | str | Country of incorporation | `"USA"` |
| `Market Cap` | float | Numeric market cap (e.g., `"1.2B"` -> `1200000000.0`); `"N/A"` for missing | `2890000000000.0` |
| `P/E` | str | Price-to-earnings ratio (kept as string; can be `"-"`) | `"28.52"` |
| `Price` | str | Current stock price (string) | `"182.63"` |
| `Change` | str | Daily price change with `%` | `"-1.23%"` |
| `Volume` | str | Daily trading volume (comma-separated string) | `"52,436,789"` |
| `Symbol` | str | Raw ticker symbol (added by the post-parse step) | `"AAPL"` |

**Sort order**: as returned by Finviz (its default sort for view `v=111`). The screener does not re-sort.

### 4.2 `funda_insight_result_unfiltered_*.csv`

Produced by `fundainsight/app/picker.py` after enrichment + ratio calculation, before filters.

Includes all surviving columns from the screener DataFrame plus:

| Column | dtype | Description |
|---|---|---|
| `Symbol` | str | Ticker symbol |
| `Market Cap` | float | From Yahoo `summary_detail.marketCap` |
| `Shares Outstanding` | int | From Yahoo `key_stats.sharesOutstanding` |
| `Total Assets` | float | From Yahoo `balance_sheet.TotalAssets` |
| `Adjusted Total Assets` | float \| None | After subtracting `Goodwill` and `OtherNonCurrentAssets` |
| `Adjusted Total Current Assets` | float \| None | After subtracting `OtherCurrentAssets` and adding back 30% of `Inventory` |
| `Total Equity` | float | From Yahoo `balance_sheet.StockholdersEquity` |
| `Average Price in Last 30 Days` | float | Median `close` over the 1-month price history |
| `price_by_assets` | float | `Adjusted Total Assets / Shares Outstanding` |
| `price_by_current_assets` | float | `Adjusted Total Current Assets / Shares Outstanding` |
| `price/price_to_assets_ratio` | float | `Average Price in Last 30 Days / price_by_assets` |
| `price/price_to_current_assets_ratio` | float | `Average Price in Last 30 Days / price_by_current_assets` |

Tickers that returned `None` from `get_financial_data` are dropped before this CSV is written.

### 4.3 `funda_insight_result_*.csv`

Same shape as `funda_insight_result_unfiltered_*.csv` after the filter chain in `picker.py`:

```python
.filter_countries(["Brazil", "Chile", "India", "Bermuda", "China"])
.filter_sector("Energy")
.filter_price("price/price_to_current_assets_ratio", 1)   # keep rows where ratio < 1
```

The country / sector / threshold list is currently hardcoded; configurability is queued tech debt (see `CLAUDE.md`).

### 4.4 Encoding

UTF-8, default pandas `to_csv` settings. The Excel `=HYPERLINK(...)` formula in the `Ticker` column is intentional — when opened in Excel or Google Sheets, the ticker becomes a clickable link to Finviz. CSV-injection risk is acknowledged: the `=` prefix is a potential vector if a future column accepts user-supplied text. The current columns are all from trusted sources (Finviz HTML), so this is rated low; revisit when adding any user-input column.

---

## 5. Configuration Contract

### 5.1 `Config` Pydantic model

Defined in `config/config.py`, extends `core/configuration/config_base.py:SystemSettings` (which extends Pydantic `BaseModel`).

```python
class Config(SystemSettings):
    name: str         = "Stock Screener CLI config"
    description: str  = "Configuration for the Stock Screener CLI app."
    use_history: bool = False
    filters: tuple    = ()           # tuple of (filter_key, value_code) pairs
    scrape_link: str  = ""

    def file_path(self, name: str) -> str: ...
```

### 5.2 Builder

`core/configuration/configurator.py:build_config(use_history: bool = False, filters: str = "") -> Config`

- `use_history=True` reads `<module>/local_history/filter_history.json` and populates `filters`.
- `filters=<json>` invokes `core/converters/json.py:json_to_tuples` to parse the JSON into the `filters` tuple shape.
- If both are empty, returns a `Config` with default values; the interactive UI populates `filters` later.

### 5.3 Filter history JSON

```
fincli/local_history/filter_history.json
fundainsight/local_history/filter_history.json
```

Schema:

```json
{
  "fa_pe": "u20",
  "sec": "energy",
  "geo": "usa"
}
```

Keys are Finviz filter `query_key`s (see §2.1). Values are `value_code`s. The file is overwritten on each successful run that produced a non-empty filter set.

---

## 6. Logger Contract

```python
from logger import logger
```

Returns the process-wide Singleton instance. The class is metaclass-based (`singleton.py`) so re-importing in a subprocess produces a fresh instance, but within a single process there is exactly one.

### 6.1 Public methods

- `logger.debug(msg: str) -> None`
- `logger.info(msg: str) -> None`
- `logger.warning(msg: str) -> None`
- `logger.error(msg: str) -> None`

`msg` is a single string. Use f-strings to interpolate; do not pass positional `%` args.

### 6.2 Handlers attached at construction

| Handler | Output | Level |
|---|---|---|
| Typing-effect console handler | `stdout` with simulated typing animation | INFO+ |
| Plain console handler | `stdout` with no animation | DEBUG+ |
| File handler — activity log | `logs/activity.log` | DEBUG+ |
| File handler — error log | `logs/error.log` | ERROR+ |
| JSON file handler | `logs/<dynamic>.json` (per-call when used) | DEBUG+ |

Handler set is fixed at instance construction. Adding or removing handlers at runtime is not part of the contract.

### 6.3 Format

Console (typing or plain):
```
{title} {message}
```
`title` is colorized via `colorama` based on level.

Activity log:
```
{ISO timestamp}  {level}  {title}  {message}
```

Error log:
```
{ISO timestamp}  {level}  {module}:{function}:{line}  {title}  {message}
```

### 6.4 Thread safety

The underlying stdlib `logging.Logger` handlers are thread-safe. The typing-animation console handler serializes its writes under the same lock. Concurrent `logger.info`, `logger.error`, etc. from `ThreadPoolExecutor` workers in `picker.py` are safe.

---

## 7. Internal Service Interfaces (importable surface)

These functions and classes are imported across modules. Keep their signatures stable.

### 7.1 `fincli/app/main.py`

```python
def run_stock_screener(history: bool = False, debug: bool = False) -> None
def fetch_urls(quarry: str, page_count: int) -> list[bytes]
def aggregate_rows(pages: list[bytes]) -> list[list]
def build_data_frame(data_rows: list[list]) -> pandas.DataFrame
def convert_market_cap_to_numeric(market_cap: str) -> float | str
```

### 7.2 `fundainsight/app/main.py`

```python
def get_opportunities(
    history: bool = False,
    debug: bool = False,
    set_filters: str = "",
    scrape_link: str = "",
) -> pandas.DataFrame | None
```

### 7.3 `fundainsight/app/picker.py`

```python
def picker(df: pandas.DataFrame | None) -> pandas.DataFrame | None
def add_new_columns(df: pandas.DataFrame) -> pandas.DataFrame
def assign_old_df_to_new_df(
    old_df: pandas.DataFrame,
    new_df: pandas.DataFrame,
    column: str,
) -> pandas.DataFrame
```

### 7.4 `fundainsight/calculators/equity_calc.py`

```python
def get_financial_data(ticker_name: str) -> dict | None
def calculate_price_to_data(financial_data: dict, column_name: str) -> float
def ratio_between_two_values(value1: float, value2: float) -> float
def adjust_assets(
    balance_sheet: pandas.DataFrame,
    asset_type: str,
    adjustment_factor: float,
    additional_subtracts: list[str],
) -> float | None
```

### 7.5 `fundainsight/calculators/filters.py`

```python
class Filters:
    def __init__(self, df: pandas.DataFrame) -> None: ...
    def filter_country(self, country: str) -> "Filters": ...
    def filter_countries(self, countries: list[str]) -> "Filters": ...
    def filter_sector(self, sector: str) -> "Filters": ...
    def filter_price(
        self,
        column: str,
        price: float,
        less_than: bool = True,
    ) -> "Filters": ...
    def get_data(self) -> pandas.DataFrame: ...
```

### 7.6 `core/configuration/configurator.py`

```python
def build_config(use_history: bool = False, filters: str = "") -> Config
```

### 7.7 `core/converters/json.py`

```python
def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]
```

### 7.8 `fincli/utils/web_scraper.py`

```python
def fetch_page_sync(url: str) -> bytes
```

### 7.9 `fincli/utils/quary_builders.py`

```python
def build_stock_screener_query(
    filters_tuple: tuple,
    v: int = 111,
    ft: int = 2,
) -> str
```

---

## 8. Stability Policy

A change is **breaking** if it alters any of:

- A CLI option name, alias, type, or default.
- A CLI exit-code convention.
- A Finviz filter `query_key`, `value_code`, or display name (because `filter_history.json` references these by name).
- The shape of any CSV column listed in §4 (rename, drop, dtype change).
- The Yahoo Finance fields read in §3 (adding more is fine; removing or renaming is not).
- The `Config` field set in §5.1 (adding new fields with safe defaults is fine; renaming or removing is not).
- The `logger` Singleton method names in §6.1.
- Any `def` signature in §7.

When a breaking change is unavoidable:

1. **Bump a documented version**. There is no formal SemVer release today, so until one exists, stamp the change with the date in the commit message and update `docs/FEEDBACK-LOG.md` with a `### YYYY-MM-DD — <topic>` entry summarizing what changed and why.
2. **Call it out in the commit message** — a `BREAKING:` prefix is appropriate. A future-self reading `git log` should see breakage at a glance.
3. **Update `CLAUDE.md` tech-debt section** if a migration step is required of users (e.g., delete an old `filter_history.json`, regenerate output, etc.).

Non-breaking additions (new CLI options with defaults, new CSV columns appended at the end, new Pydantic fields with defaults, new public functions in §7) need no special ceremony beyond a routine commit.
