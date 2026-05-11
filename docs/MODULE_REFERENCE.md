# MODULE_REFERENCE.md — Fin CLI Internal Module Reference

This file documents the internal modules of Fin CLI. There is no REST API to document — the public surface is a CLI, and the internal boundaries are importable Python packages. Each section follows a fixed structure: Purpose / Key files / Public surface / Data shapes / Error modes / Integration.

See `ARCHITECTURE.md` for the system-level diagram and data-flow narrative. See `docs/THESIS.md` for vision and roadmap.

---

## Table of Contents

1. [`fincli/`](#fincli) — Finviz stock screener
2. [`core/`](#core) — Configuration framework
3. [`config/`](#config) — Project-level settings
4. [`logger/`](#logger) — Singleton logger

---

## `fincli/`

### Purpose

Stock screener. Builds a Finviz.com query URL from user-selected filter values, fetches all paginated HTML result pages through `cfscrape` (Cloudflare-bypassing HTTPS client), parses the HTML stock table with BeautifulSoup, assembles a `pandas.DataFrame`, and writes a timestamped CSV to `workspace_output/`.

This module operates entirely synchronously — no threading.

### Key files

| File | Role |
|------|------|
| `fincli/app/cli.py` | Click entry point. Defines the `@click.group` with `--history`, `--debug` flags. Invokes `run_stock_screener`. |
| `fincli/app/main.py` | Orchestrator. `run_stock_screener(history, debug)` → `fetch_urls(quarry, page_count)` → `aggregate_rows(pages)` → `build_data_frame(rows)` → `convert_market_cap_to_numeric(df)`. Writes the final CSV. |
| `fincli/cli/cli_stock_screener.py` | Interactive filter-selection UI. The `prompt_section` helper displays each filter group (Fundamental / Descriptive / Technical) one at a time using **per-section local 1-based numbering**; the user enters comma-separated numbers for that section, or presses Enter alone to skip it. Out-of-range / non-integer input reprompts cleanly. Returns a list of `(query_key, value_code)` tuples. |
| `fincli/utils/web_scraper.py` | `fetch_page_sync(url)` — makes one HTTPS request via `cfscrape` with a randomized User-Agent and 10-second timeout. Implements exponential backoff on rate-limit responses. |
| `fincli/utils/quary_builders.py` | `build_stock_screener_query(filters)` — takes the list of selected filter tuples and assembles the Finviz screener URL (`https://finviz.com/screener.ashx?v=111&f=<codes>&ft=2`). Handles pagination by appending `&r=<offset>`. |
| `fincli/stock_screening/content/stock_table.py` | Top-level HTML table extractor. Uses BeautifulSoup to locate the screener result table and extract all rows. |
| `fincli/stock_screening/parsers/stock_table.py` | Per-row HTML cell parser. Converts raw `<td>` cell text to typed Python values (strings, floats, ints). |
| `fincli/stock_screening/locators/stock_table_locators.py` | CSS / element locators for the Finviz screener table — used by both the content extractor and the per-row parser to keep selectors in one place. |
| `fincli/resource/params/fundamental_params.py` | Filter parameter definitions for Finviz fundamental filters (P/E, ROE, profit margin, debt/equity, etc.). Format: `[query_key, {value_code: display_name}]`. |
| `fincli/resource/params/descriptive_params.py` | Filter parameter definitions for Finviz descriptive filters (sector, country, market cap, exchange, etc.). Same format. |
| `fincli/resource/params/technical_params.py` | Filter parameter definitions for Finviz technical filters (RSI, SMA, performance, short float, etc.). Same format. |

### Public surface

CLI commands only. No importable API is intended for external callers.

```
python -m fincli                    # interactive filter selection
python -m fincli --history          # reuse last filter selection
python -m fincli --debug            # verbose logging
```

Internal function signatures (for testing):

```python
# fincli/app/main.py
def run_stock_screener(history: bool = False, debug: bool = False)
    # Builds config internally via build_config(use_history=history).
    # Does NOT accept a Config argument and does NOT return a DataFrame to the caller.
    # Writes the final CSV to workspace_output/ and returns None on both success and failure.
def fetch_urls(quarry, page_count)
    # Fetches page_count pages from the Finviz query URL quarry.
    # Constructs paginated URLs by appending &r=<offset> and delegates each to
    # fetch_page_sync. Returns a list[str] where each element is the raw HTML
    # of one result page.
def aggregate_rows(pages: list[str]) -> list[dict]    # parsed rows from all pages
def build_data_frame(rows: list[dict]) -> DataFrame
def convert_market_cap_to_numeric(df: DataFrame) -> DataFrame
```

### Data shapes

Output `DataFrame` columns (from Finviz screener table — exact column set depends on Finviz layout):

| Column | Type | Notes |
|--------|------|-------|
| `Symbol` | `str` | Ticker symbol |
| `Company` | `str` | Company name |
| `Sector` | `str` | GICS sector string |
| `Country` | `str` | Country of domicile |
| `Market Cap` | `float` | Numeric (converted from Finviz abbreviated string by `convert_market_cap_to_numeric`) |
| `P/E` | `float` | Trailing price-to-earnings |
| ... | ... | Other Finviz columns depending on screener view |
| `Ticker` (Excel) | `str` | `=HYPERLINK(...)` formula wrapping the symbol — preserved for Excel use |

Filter history saved as `<Config.history_dir>/filter_history.json`. The directory comes from `Config.history_dir` (default: platformdirs `user_data_dir("fincli", appauthor=False) / "local_history"`; overrideable via `HISTORY_DIR` env var read in `build_config`). See `CONTRACTS.md` §4.1 for the full contract.

CSV written to: `workspace_output/stock_screener_{YYYY-MM-DD_HH-MM}.csv`.

### Error modes

| Condition | Behavior |
|-----------|----------|
| Cloudflare rate-limit (HTTP 429 or 503) | `fetch_page_sync` applies exponential backoff and retries. On exhaustion, logs error and raises. |
| HTML parse failure (unexpected Finviz layout change) | BeautifulSoup returns empty list; `aggregate_rows` yields no rows; `build_data_frame` returns empty DataFrame; logged as warning. |
| Network timeout (10-second limit) | Exception propagated; caller logs and skips the page. |
| `--history` with missing `filter_history.json` | `build_config` raises `FileNotFoundError`; the user re-runs without the flag for interactive selection. |

### Integration

- **Depends on** `core/` for config building, `config/` for the `Config` class, `logger/` for the Singleton logger.
- No reverse dependencies — nothing in this repo imports from `fincli/`.

---

## `core/`

### Purpose

Pure-Python configuration framework. Provides Pydantic base classes, a generic `Configurable[S]` protocol, a `build_config` factory that wires config loading + history, and a JSON-to-tuples converter for parsing JSON filter input. Has no external service dependencies.

### Key files

| File | Role |
|------|------|
| `core/configuration/config_base.py` | `SystemSettings(BaseModel)` — Pydantic base class with `use_history: bool`, `filters: list`, `scrape_link: str`, `debug: bool`. `Configurable[S]` generic protocol. |
| `core/configuration/configurator.py` | `build_config(use_history, filters)` — constructs and returns a `Config` instance; when `use_history=True`, reads `config.history_dir / 'filter_history.json'` (default and override per CONTRACTS §4.1); otherwise parses the JSON filter string when `filters` is provided. |
| `core/converters/json.py` | `json_to_tuples(json_str)` — parses a JSON filter string into a list of `(query_key, value_code)` tuples for consumption by the Finviz URL builder. |

### Public surface

```python
# core/configuration/config_base.py
class SystemSettings(BaseModel):
    use_history: bool
    filters: list
    scrape_link: str
    debug: bool

# core/configuration/configurator.py
def build_config(use_history: bool = False, filters: str = "") -> Config
    # Returns a concrete Config instance (not a generic S).
    # The Configurable[S] generic defined in config_base.py is NOT used by
    # build_config — it is a protocol for future extension only.

# core/converters/json.py
def json_to_tuples(json_str: str) -> list[tuple[str, str]]
```

### Data shapes

- `SystemSettings` fields are validated by Pydantic on construction. Any invalid type raises `pydantic.ValidationError` before execution reaches the CLI body.
- `filter_history.json` is a JSON object mapping filter category names to selected value codes: `{"category": "value_code", ...}`. Written and read by `build_config`.
- `json_to_tuples` input: a JSON string like `{"fa_pe_low": "u5", "geo_country_usa": "usa"}`. Output: `[("fa_pe_low", "u5"), ("geo_country_usa", "usa")]`.

### Error modes

| Condition | Behavior |
|-----------|----------|
| Invalid config field type | `pydantic.ValidationError` raised at startup; CLI exits with error message. |
| `filter_history.json` missing when `--history` is set | `build_config` raises `FileNotFoundError`; the user re-runs without the flag for interactive selection. |
| Malformed filter JSON string | `json_to_tuples` raises `json.JSONDecodeError`; caller logs and exits. |

### Integration

- **Consumed by** `fincli/app/cli.py` at startup via `build_config`.
- **Extended by** `config/config.py` which defines the concrete `Config` class.
- **No external dependencies** — plain Pydantic, `json`, `os`. This is intentional to keep the framework portable.

---

## `config/`

### Purpose

Project-level Pydantic settings. Defines the concrete `Config` class that the screener instantiates. Extends `SystemSettings` with the `file_path(name)` helper that generates timestamped CSV output paths.

### Key files

| File | Role |
|------|------|
| `config/config.py` | `Config(SystemSettings)` — adds `file_path(name: str) -> str` which returns `workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv`. Used everywhere a CSV output path is needed. |

### Public surface

```python
# config/config.py
class Config(SystemSettings):
    def file_path(self, name: str) -> str: ...
```

Usage pattern:

```python
from config import config
path = config.Config.file_path("my_output")
# -> "workspace_output/my_output_2026-05-04_14-30.csv"
```

### Data shapes

- `Config` inherits all fields from `SystemSettings`.
- `file_path` output is always under `workspace_output/` (the directory is created if it does not exist). The timestamp is `strftime("%Y-%m-%d_%H-%M")` at call time.

### Error modes

| Condition | Behavior |
|-----------|----------|
| `workspace_output/` does not exist | `file_path` creates it on first call; no error. |
| Invalid `SystemSettings` field at instantiation | `pydantic.ValidationError` propagated to caller. |

### Integration

- **Instantiated by** `core/configuration/configurator.py` via `build_config`.
- **Imported directly** by `fincli/app/main.py` as `from config import config` for the `file_path` call.
- **Does not** import from `fincli/` — no circular dependency.

---

## `logger/`

### Purpose

Singleton logger with three handlers: a typing-effect console handler (colorama ANSI), a plain console handler, and a JSON file handler. Imported everywhere as `from logger import logger`. The Singleton is metaclass-based (`singleton.py` at repo root).

### Key files

The `logger/` package is a flat set of files — there are no subdirectories.

| File | Role |
|------|------|
| `logger/__init__.py` | Package init; re-exports the logger singleton. |
| `logger/logger.py` | `Logger` class (Singleton). Exposes `.info`, `.warning`, `.error`, `.debug`. Initializes all three handlers on first construction; subsequent imports return the same instance. |
| `logger/handlers.py` | Three handler classes in a single file: `ConsoleHandler` (plain stdout, extends `logging.StreamHandler`), `TypingConsoleHandler` (typing-animation word-by-word output, extends `logging.StreamHandler`), `JsonFileHandler` (structured JSON to a log file, extends `logging.FileHandler`). |
| `logger/formatters.py` | Two formatter classes: `AlgoFormatter` (supports `color` and `title` log extras; produces ANSI-colored output via colorama `Style`), `JsonFormatter` (passes the raw message through as JSON). Also contains `remove_color_codes(s)` helper. |
| `logger/log_cycle.py` | Internal typing-animation state machine used by `TypingConsoleHandler`. |
| `singleton.py` (repo root) | Metaclass `Singleton` — ensures only one instance of `Logger` exists per process. Imported by `logger.py`. |

### Public surface

```python
# The only correct import pattern:
from logger import logger

logger.info("message")
logger.warning("message")
logger.error("message")
logger.debug("message")
```

Handlers are not part of the public surface — they are initialized internally and must not be instantiated directly.

### Data shapes

- Console output: ANSI-colored text with typing animation (configurable speed) or plain text.
- JSON file output (`logs/activity.log`): one JSON object per line — `{"timestamp": "...", "level": "INFO", "message": "...", "caller": "..."}`.
- `logs/error.log`: same format, ERROR+ only.

### Error modes

| Condition | Behavior |
|-----------|----------|
| Handler init failure (e.g., `logs/` directory missing) | Falls back to bare `print` on the console. No crash. |
| Multiple `Logger()` constructor calls | Metaclass returns the existing instance; no duplicate handlers. |
| Typing animation interrupted (KeyboardInterrupt) | Animation stops cleanly; output may be truncated mid-line. |

### Integration

- **Imported by** every module in `fincli/`, `core/`, and `config/`.
- **Thread safety** — `TypingConsoleHandler` holds an internal lock to prevent interleaved output. The JSON file handlers are stateless (no shared mutable state between calls).
- **No reverse dependencies** — `logger/` does not import from any other local package.

---

*Last updated: 2026-05-04. Maintained alongside source changes — update this file whenever a module's public surface, key files, or error modes change.*
