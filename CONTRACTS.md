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
| `--scrape-link` | — | string | `""` | Direct Finviz screener URL; bypasses interactive filter selection. Empty string keeps the interactive flow. |
| `--filter` | — | repeatable string | `()` | Single Finviz filter as `key=value`; repeatable. Example: `--filter fa_pe=u20 --filter sec=energy`. |
| `--filters-json` | — | string | `""` | Inline flat-object JSON dict of filters, e.g. `--filters-json '{"fa_pe":"u20"}'`. Schema validated by `core.converters.json.json_to_tuples` (see §6.3). |
| `--filters-file` | — | path | `None` | Path to a JSON file containing the same flat-object payload. Path is validated by Click (`exists=True, dir_okay=False, readable=True`). |
| `--output` | `-o` | string | `""` | Exact CSV destination. Parent dir must exist. No timestamp added; overwrites if the file exists. Use `-` to stream CSV to stdout. Orthogonal to all input-mode flags. |

**Mutual-exclusion set:** `--filter`, `--filters-json`, `--filters-file`, `--history`, `--scrape-link`. At most one input mode may be set; passing two or more raises `click.UsageError` (exit 2) with the canonical message `--filter / --filters-json / --filters-file / --history / --scrape-link are mutually exclusive; pick one input mode.` See `docs/features/pipeline-mode-spec.md` §6.2. Note: `--output` is **not** in this set — it composes with any input mode.

**Behavior**

| State | What happens |
|---|---|
| No subcommand, no input-mode flag | Section-by-section interactive filter selection. Each filter group (Fundamental / Descriptive / Technical) is displayed in turn with **per-section local 1-based numbering**; the user enters comma-separated numbers for that section, or presses Enter alone to skip it. **Bounds-checked input**: out-of-range or non-integer values are rejected with a clear message and the same section reprompts (no `IndexError`). After all three sections, the screener pipeline runs and the CSV is written. The selected filters are persisted to `<Config.history_dir>/filter_history.json` for `--history` reuse. |
| `--history` | Skip the interactive menu; reuse the last filter set. |
| `--scrape-link=<url>` | Skip the interactive menu **and** the filter-to-URL query builder; fetch the supplied URL verbatim. No URL validation is performed — invalid URLs surface as downstream HTTP errors. `filter_history.json` is **not** overwritten on this path (no filter set to record). |
| `--filter K=V [...]` / `--filters-json '{...}'` / `--filters-file PATH` | Skip the interactive menu; populate `Config.filters` from the supplied structured input. Keys and values are validated against the registered Finviz inventory (see `fincli/resource/params/validators.py`); unknowns raise `UsageError` (exit 2) before any HTTP fetch. The selection is persisted to `filter_history.json` for `--history` reuse. |
| Two or more input-mode flags set | Rejected at parse time with a `UsageError` (alternative input modes, undefined when combined). |
| `--debug` | Logger level lowered to `DEBUG` for the duration of the run. |
| `--output PATH` | CSV is written to exactly `PATH`. Filename is **not** timestamped; overwrites silently if the file exists. Composes with any input-mode flag. Precedence: `--output PATH` > `--output -` > `FINCLI_OUTPUT_DIR` > default. |
| `--output -` | CSV bytes are streamed to **stdout**. **Stdout contains only CSV bytes**: the two console handlers (typing-effect + plain) are rerouted to stderr at run start, the welcome banner is suppressed, and the previously stdout-bound `Base Url:` echo from the query builder is removed (the URL is still logged at INFO via the rerouted logger). Log progress, banner location, errors all land on stderr. The default `Ticker` HYPERLINK formula stripping for stdout mode is **not yet implemented** (Pillar 6); `--output -` writes the same shape today as `--output PATH`. |
| `FINCLI_OUTPUT_DIR=<dir>` env var | Replaces the parent directory of the default `workspace_output/stock_screener_{date}.csv` while preserving the timestamped basename. Loses to an explicit `--output PATH`. Read by `core.configuration.configurator.build_config`. |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | Run completed; CSV written. |
| non-zero | Unhandled exception bubbled to the Click runner. The traceback is printed to stderr and written to `logs/error.log`. |

**Output side effects**

- CSV destination resolved via the Pillar-2 precedence chain: `--output PATH` > `--output -` (stdout stream) > `FINCLI_OUTPUT_DIR=<dir>` env var (parent-dir override) > default `workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv` under CWD.
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
| `Market Cap` | nullable `Float64` (empty cell for missing/unparseable) | Numeric market cap (e.g., `"1.2B"` -> `1200000000.0`). **N/A semantics:** Finviz tokens `"-"`, `"_"`, `""`, `"N/A"` (any case) and any unparseable cell coerce to `pandas.NA` and serialize as an empty CSV cell — never the literal string `"nan"`, `"<NA>"`, or `0.0`. Contract enforced by `fincli.utils.market_cap.convert_market_cap_to_numeric` per `docs/features/pipeline-mode-spec.md` §5.5. | `2890000000000.0` |
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
    name: str             = "Stock Screener CLI config"
    description: str      = "Configuration for the Stock Screener CLI app."
    use_history: bool     = False
    filters: tuple        = ()           # tuple of (filter_key, value_code) pairs
    scrape_link: str      = ""
    history_dir: Path     = Field(default_factory=lambda: Path(user_data_dir("fincli", appauthor=False)) / "local_history")
    output_path: str      = ""           # `--output PATH` / `--output -` (sentinel)
    output_dir: Path | None = None       # `FINCLI_OUTPUT_DIR` env override

    def file_path(self, name: str) -> str: ...
```

`history_dir` is the directory containing `filter_history.json`. The default resolves via `platformdirs.user_data_dir("fincli")` to an absolute path under the user's data directory — `%LOCALAPPDATA%\fincli\local_history\` on Windows, `~/Library/Application Support/fincli/local_history/` on macOS, `~/.local/share/fincli/local_history/` on Linux — so `fincli --history` works from any CWD. The default is overrideable via the `HISTORY_DIR` env var (read by `core.configuration.configurator.build_config`) or Pydantic init (`Config(history_dir=Path("..."))`). This is a behavioral default change from the prior CWD-relative `Path("fincli/local_history")` shipped 2026-05-09; existing `fincli/local_history/filter_history.json` caches will not auto-migrate — see §4.3 and the archived reviewer note `docs/reviewer/archive/history-dir-cwd-portability.md`.

`output_path` is the caller-pinned CSV destination from `--output PATH` (or the `-` sentinel for stdout streaming). Empty string means "no caller pin"; precedence then falls through to `output_dir`, then to the CWD-relative default. The module-level constant `config.config.STDOUT_SENTINEL` (value `"-"`) names the stdout-streaming sentinel so the literal `"-"` is greppable across `Config.file_path` and `run_stock_screener`'s dispatch site.

`output_dir` is the parent-directory override sourced from the `FINCLI_OUTPUT_DIR` env var (read by `core.configuration.configurator.build_config`). When set, `Config.file_path` keeps the timestamped basename and writes under `<output_dir>/`. Loses to `output_path` per the precedence chain.

`Config.file_path(name)` is an instance method (not a `@staticmethod`) so all three precedence tiers — explicit path, env-override directory, default — are resolved at one site. The stdout sentinel intentionally **does not** affect `file_path`'s output: the dispatch (file vs stdout) lives at the orchestrator boundary in `run_stock_screener`, so callers that hit `file_path` cannot accidentally produce a file literally named `-`. Spec: `docs/features/pipeline-mode-spec.md` §5.2.

### 4.2 Builder

`core/configuration/configurator.py:build_config(use_history: bool = False, filters: str = "", scrape_link: str = "", output_path: str = "") -> Config`

- `use_history=True` reads `<Config.history_dir>/filter_history.json` (path resolved per §4.1) and populates `filters`.
- `filters=<json>` invokes `core/converters/json.py:json_to_tuples` to parse the JSON into the `filters` tuple shape.
- `scrape_link=<url>` populates `Config.scrape_link` to bypass query construction.
- `output_path=<path>` populates `Config.output_path` (Pillar 2 destination pin); empty string falls through to env / default.
- The `FINCLI_OUTPUT_DIR` env var, when set, populates `Config.output_dir` as the parent-directory override (loses to `output_path`).
- The `HISTORY_DIR` env var, when set, populates `Config.history_dir`.
- If all are empty, returns a `Config` with default values; the interactive UI populates `filters` later.

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

Keys are Finviz filter `query_key`s (see §2.1). Values are `value_code`s. The file is overwritten on each successful run that produced a non-empty filter set, regardless of input mode (interactive picker, `--filter`, `--filters-json`, or `--filters-file`). The `--scrape-link` and `--history` paths do **not** overwrite the file (`--scrape-link` has no filter set to record; `--history` is the read path).

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
| Typing-effect console handler | `stdout` with simulated typing animation (retargetable via `Logger.set_console_stream`) | INFO+ |
| Plain console handler | `stdout` with no animation (retargetable via `Logger.set_console_stream`) | DEBUG+ |
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
def run_stock_screener(
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filters: str = "",
) -> None
def fetch_urls(quarry: str, page_count: int) -> list[bytes]
def aggregate_rows(pages: list[bytes]) -> list[list]
def build_data_frame(data_rows: list[list]) -> pandas.DataFrame
```

`filters` is a JSON string in the canonical flat-object shape (see §6.3). The CLI normalizes the three structured-input flag forms (`--filter`, `--filters-json`, `--filters-file`) into this single string before calling. Empty string means "interactive flow" or "use whichever other input mode is set" (`--history` / `--scrape-link`).

### 6.2 `core/configuration/configurator.py`

```python
def build_config(use_history: bool = False, filters: str = "", scrape_link: str = "") -> Config
```

### 6.3 `core/converters/json.py`

```python
def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]
```

**Schema (locked down 2026-05-15, commit landing Pillar 1):** the JSON literal must decode to a **flat object** whose values are all strings. The empty object `{}` is allowed (returns `()` — the no-filters case). Any other shape — top-level array, scalar, or null; nested objects, arrays, numbers, booleans, or null as values — raises `ValueError` (which the CLI translates to `click.UsageError`, exit 2). This is the same shape `filter_history.json` (§4.3) uses; one schema across the system. Single quotes in the input are normalized to double quotes for shell-friendly usage. See `docs/features/pipeline-mode-spec.md` §5.1 step 3 (OQ1 resolution).

**Compatibility note:** Previously the converter also accepted `[["k","v"]]` lists; that path now raises. Per §7, this is framed as a **conformance fix** (the legacy list-shape path silently fed unvalidated key-value pairs into `quary_builders.build_stock_screener_query`, which then silently dropped unknowns — exactly the silent-corruption failure mode `THESIS.md` Design Principle #2 prohibits) rather than a SemVer-style break. Mirrors the §3.1 / market-cap precedent: tightening an implementation toward the documented contract is a fix, not a redefinition. To be recorded in `docs/FEEDBACK-LOG.md` by Task 6 of the pipeline-mode rollout.

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

### 6.6 `fincli/utils/market_cap.py`

```python
def convert_market_cap_to_numeric(value: str | None) -> float | pandas.NA
```

Carved out of `fincli/app/main.py` (commit `50f46ca`, 2026-05-15) so the parser is directly testable. See §3.1 for the full input/output contract and `docs/features/pipeline-mode-spec.md` §5.5 for the design rationale.

### 6.7 `fincli/resource/params/validators.py`

```python
def validate_filter_pairs(pairs: tuple[tuple[str, str], ...]) -> None
def list_valid_filters() -> dict[str, list[str]]
```

`validate_filter_pairs` is the single chokepoint that closes the silent-drop hazard at `fincli/utils/quary_builders.py:18-22` for structured input: it raises `click.UsageError` when any pair has an unknown query_key or an unknown value_code-for-known-key. The error message names the offending token and lists up to 10 valid alternatives. Called from `core.configuration.configurator.build_config` immediately after `json_to_tuples`. The `--scrape-link` and `--history` input modes deliberately skip this validator (URL is opaque; history was previously valid by construction). The interactive picker UI is also skipped — its bounds-checked input already guarantees valid pairs.

`list_valid_filters` returns the same `{query_key: [value_code, ...]}` inventory the validator walks. Used to power the inline error-message suggestions, and reserved for a future `--help-filters` CLI flag (deferred per spec §9).

Carved out (commit landing Pillar 1, 2026-05-15) per `docs/features/pipeline-mode-spec.md` §5.1 step 5.

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
