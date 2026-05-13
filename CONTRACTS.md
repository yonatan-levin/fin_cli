# CONTRACTS.md - Fin CLI Contracts

This document defines the **stable surfaces** that other code (downstream automation, Phase 2 tests, future modules) and end users rely on. A contract here is a promise: changing it is a breaking change, governed by the stability policy at the bottom of this file.

Fin CLI has **no REST API, no HTTP listener, no broker integration, no database**. It is a CLI plus a set of importable Python packages, plus the CSV it writes. The contracts therefore live in five places:

1. The **CLI command surface** — every Click command, every option, every exit code.
2. The **Finviz query parameter contract** — the `[query_key, {value_code: display_name}]` filter shape under `fincli/resource/params/`.
3. The **CSV output schema** — column names, dtypes, sort order, file naming.
4. The **Configuration shape** — the Pydantic-validated `Config` produced by `core/configuration/configurator.py`.
5. The **logger contract** — what `from logger import logger` returns and what its methods promise.

---

## 1. CLI Command Surface

**Entry points:** `fincli` (preferred, registered via `[project.scripts]` in `pyproject.toml`) and `python -m fincli` (canonical fallback, useful when the venv's `Scripts/` dir is not on PATH). Both resolve to `fincli/app/cli.py:run_main`.

```
Usage: python -m fincli [OPTIONS]   (equivalent: fincli [OPTIONS])

  Welcome to the Stock Screener CLI!
```

| Option | Alias | Type | Default | Description |
|---|---|---|---|---|
| `--history` | `--hist` | flag | `False` | Reload the most recent filter selection from `<Config.history_dir>/filter_history.json` (see §4.1 for the default + override) instead of prompting interactively. |
| `--debug` | — | flag | `False` | Set the logger level to `DEBUG`. |
| `--scrape-link` | — | string | `""` | Direct Finviz screener URL; bypasses interactive filter selection. Empty string keeps the interactive flow. Mutually exclusive with `--history` — combining them exits non-zero with a Click `UsageError`. |

**Behavior**

| State | What happens |
|---|---|
| No subcommand, no `--history`, no `--scrape-link` | Section-by-section interactive filter selection. Each filter group (Fundamental / Descriptive / Technical) is displayed in turn with **per-section local 1-based numbering**; the user enters comma-separated numbers for that section, or presses Enter alone to skip it. **Bounds-checked input**: out-of-range or non-integer values are rejected with a clear message and the same section reprompts (no `IndexError`). After all three sections, the screener pipeline runs and the CSV is written. |
| `--history` | Skip the interactive menu; reuse the last filter set. |
| `--scrape-link=<url>` | Skip the interactive menu **and** the filter-to-URL query builder; fetch the supplied URL verbatim. No URL validation is performed — invalid URLs surface as downstream HTTP errors. |
| `--history --scrape-link=<url>` | Rejected at parse time with a `UsageError` (alternative input modes, undefined when combined). |
| `--debug` | Logger level lowered to `DEBUG` for the duration of the run. |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | Run completed; CSV written. |
| non-zero | Unhandled exception bubbled to the Click runner. The traceback is printed to stderr and written to `logs/error.log`. |

**Output side effects**

- `workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv`
- `<Config.history_dir>/filter_history.json` is overwritten with the current filter selection on a successful run. (See §4.1 for the default value and `HISTORY_DIR` env-var override.)
- `logs/activity.log` (DEBUG+) and `logs/error.log` (ERROR+) appended.

### 1.1 Convenience launchers

| File | Behavior |
|---|---|
| `run.sh` | Linux / macOS Bash launcher; checks the requirements then invokes `python -m fincli "$@"`. |
| `run.bat` | Windows batch equivalent. |

These are not contractually distinct from the `python -m fincli` invocation. The launchers intentionally retain `python -m fincli` (rather than the bare `fincli` shell command) for portability — the module-execution form works whether or not the editable install's `Scripts/` directory is on `PATH`.

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

## 3. CSV Output Schema

Output lands in `workspace_output/`. File names follow the pattern produced by `Config.file_path(name)`:

```
workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv
```

The minute-level timestamp lets multiple runs in a single hour coexist without collision.

### 3.1 `stock_screener_*.csv`

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

### 3.2 Encoding

UTF-8, default pandas `to_csv` settings. The Excel `=HYPERLINK(...)` formula in the `Ticker` column is intentional — when opened in Excel or Google Sheets, the ticker becomes a clickable link to Finviz. CSV-injection risk is acknowledged: the `=` prefix is a potential vector if a future column accepts user-supplied text. The current columns are all from trusted sources (Finviz HTML), so this is rated low; revisit when adding any user-input column.

---

## 4. Configuration Contract

### 4.1 `Config` Pydantic model

Defined in `config/config.py`, extends `core/configuration/config_base.py:SystemSettings` (which extends Pydantic `BaseModel`).

```python
class Config(SystemSettings):
    name: str         = "Stock Screener CLI config"
    description: str  = "Configuration for the Stock Screener CLI app."
    use_history: bool = False
    filters: tuple    = ()           # tuple of (filter_key, value_code) pairs
    scrape_link: str  = ""
    history_dir: Path = Field(default_factory=lambda: Path(user_data_dir("fincli", appauthor=False)) / "local_history")

    def file_path(self, name: str) -> str: ...
```

`history_dir` is the directory containing `filter_history.json`. The default resolves via `platformdirs.user_data_dir("fincli")` to an absolute path under the user's data directory — `%LOCALAPPDATA%\fincli\local_history\` on Windows, `~/Library/Application Support/fincli/local_history/` on macOS, `~/.local/share/fincli/local_history/` on Linux — so `fincli --history` works from any CWD. The default is overrideable via the `HISTORY_DIR` env var (read by `core.configuration.configurator.build_config`) or Pydantic init (`Config(history_dir=Path("..."))`). This is a behavioral default change from the prior CWD-relative `Path("fincli/local_history")` shipped 2026-05-09; existing `fincli/local_history/filter_history.json` caches will not auto-migrate — see §4.3 and the archived reviewer note `docs/reviewer/archive/history-dir-cwd-portability.md`.

### 4.2 Builder

`core/configuration/configurator.py:build_config(use_history: bool = False, filters: str = "") -> Config`

- `use_history=True` reads `<Config.history_dir>/filter_history.json` (path resolved per §4.1) and populates `filters`.
- `filters=<json>` invokes `core/converters/json.py:json_to_tuples` to parse the JSON into the `filters` tuple shape.
- If both are empty, returns a `Config` with default values; the interactive UI populates `filters` later.

### 4.3 Filter history JSON

```
<Config.history_dir>/filter_history.json
```

The directory comes from `Config.history_dir` (default and override per §4.1).

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

## 5. Logger Contract

```python
from logger import logger
```

Returns the process-wide Singleton instance. The class is metaclass-based (`singleton.py`) so re-importing in a subprocess produces a fresh instance, but within a single process there is exactly one.

### 5.1 Public methods

- `logger.debug(msg: str) -> None`
- `logger.info(msg: str) -> None`
- `logger.warning(msg: str) -> None`
- `logger.error(msg: str) -> None`

`msg` is a single string. Use f-strings to interpolate; do not pass positional `%` args.

### 5.2 Handlers attached at construction

| Handler | Output | Level |
|---|---|---|
| Typing-effect console handler | `stdout` with simulated typing animation | INFO+ |
| Plain console handler | `stdout` with no animation | DEBUG+ |
| File handler — activity log | `logs/activity.log` | DEBUG+ |
| File handler — error log | `logs/error.log` | ERROR+ |
| JSON file handler | `logs/<dynamic>.json` (per-call when used) | DEBUG+ |

Handler set is fixed at instance construction. Adding or removing handlers at runtime is not part of the contract.

### 5.3 Format

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

### 5.4 Thread safety

The underlying stdlib `logging.Logger` handlers are thread-safe. The typing-animation console handler serializes its writes under the same lock. Concurrent `logger.info`, `logger.error`, etc. from any future fan-out worker pool would therefore be safe.

---

## 6. Internal Service Interfaces (importable surface)

These functions and classes are imported across modules. Keep their signatures stable.

### 6.1 `fincli/app/main.py`

```python
def run_stock_screener(history: bool = False, debug: bool = False, scrape_link: str = "") -> None
def fetch_urls(quarry: str, page_count: int) -> list[bytes]
def aggregate_rows(pages: list[bytes]) -> list[list]
def build_data_frame(data_rows: list[list]) -> pandas.DataFrame
def convert_market_cap_to_numeric(market_cap: str) -> float | str
```

### 6.2 `core/configuration/configurator.py`

```python
def build_config(use_history: bool = False, filters: str = "", scrape_link: str = "") -> Config
```

### 6.3 `core/converters/json.py`

```python
def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]
```

### 6.4 `fincli/utils/web_scraper.py`

```python
def fetch_page_sync(url: str) -> bytes
```

### 6.5 `fincli/utils/quary_builders.py`

```python
def build_stock_screener_query(
    filters_tuple: tuple,
    v: int = 111,
    ft: int = 2,
) -> str
```

---

## 7. Stability Policy

A change is **breaking** if it alters any of:

- A CLI option name, alias, type, or default.
- A CLI exit-code convention.
- A Finviz filter `query_key`, `value_code`, or display name (because `filter_history.json` references these by name).
- The shape of any CSV column listed in §3 (rename, drop, dtype change).
- The `Config` field set in §4.1 (adding new fields with safe defaults is fine; renaming or removing is not).
- The `logger` Singleton method names in §5.1.
- Any `def` signature in §6.

When a breaking change is unavoidable:

1. **Bump a documented version**. There is no formal SemVer release today, so until one exists, stamp the change with the date in the commit message and update `docs/FEEDBACK-LOG.md` with a `### YYYY-MM-DD — <topic>` entry summarizing what changed and why.
2. **Call it out in the commit message** — a `BREAKING:` prefix is appropriate. A future-self reading `git log` should see breakage at a glance.
3. **Update `CLAUDE.md` tech-debt section** if a migration step is required of users (e.g., delete an old `filter_history.json`, regenerate output, etc.).

Non-breaking additions (new CLI options with defaults, new CSV columns appended at the end, new Pydantic fields with defaults, new public functions in §6) need no special ceremony beyond a routine commit.
