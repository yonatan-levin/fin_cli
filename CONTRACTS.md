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
| `--quiet` | `-q` | flag | `False` | Suppress human chatter (welcome banner + INFO/DEBUG console lines). Warnings and errors still surface. Does not change `--debug` level; debug records still land in `logs/activity.log`. Orthogonal to `--output`. |
| `--json-summary` | — | flag | `False` | Emit a single-line JSON summary of the run at end. Goes to stdout by default; routed to stderr when `--output -` streams CSV on stdout. Always the last line on its stream. Schema in §5.5. |

**Mutual-exclusion set:** `--filter`, `--filters-json`, `--filters-file`, `--history`, `--scrape-link`. At most one input mode may be set; passing two or more raises `click.UsageError` (exit 2) with the canonical message `--filter / --filters-json / --filters-file / --history / --scrape-link are mutually exclusive; pick one input mode.` See `docs/features/archive/pipeline-mode-spec.md` §6.2. Note: `--output` is **not** in this set — it composes with any input mode.

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
| `--output -` | CSV bytes are streamed to **stdout**. **Stdout contains only CSV bytes**: the two console handlers (typing-effect + plain) are rerouted to stderr at run start, the welcome banner is suppressed, and the previously stdout-bound `Base Url:` echo from the query builder is removed (the URL is still logged at INFO via the rerouted logger). Log progress, banner location, errors all land on stderr. The `Ticker` column is replaced with the raw symbol under `--output -` (the Excel `=HYPERLINK(...)` wrap is hostile to `pandas.read_csv` consumers downstream) — see §3.1 for the canonical-column note. |
| `--quiet` | Suppresses INFO/DEBUG console emission on both console handlers (typing-effect + plain) and the `click.echo` welcome banner. WARNING and ERROR records still emit. File handlers (`logs/activity.log`, `logs/error.log`) are **unaffected** — debug records under `--debug --quiet` still land in `activity.log`. Output destination is unchanged (the `OUTPUT_PATH=` stderr line still emits — pipelines need it even under `--quiet`). |
| `--json-summary` | Emit one single-line JSON object at end of run on the stream not occupied by CSV bytes: **stdout** by default, **stderr** when `--output -` is set. Always the last line on its stream. Schema in §5.5. Composes orthogonally with `--quiet` and `--debug`. |
| `FINCLI_OUTPUT_DIR=<dir>` env var | Replaces the parent directory of the default `workspace_output/stock_screener_{date}.csv` while preserving the timestamped basename. Loses to an explicit `--output PATH`. Read by `core.configuration.configurator.build_config`. |

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | **SUCCESS** — Run completed; CSV written (or streamed). Includes zero-row results: a zero-row run still writes a header-only CSV so the "every successful run produces a discoverable output" contract holds. |
| `1` | **INTERNAL** — Unexpected internal failure. Uncaught exception that escaped the orchestrator and did not match the upstream/data classifier families. Traceback is printed to stderr and written to `logs/error.log`. |
| `2` | **USAGE** — CLI input validation error. Click's default for `UsageError` and `BadParameter`. Includes the mutual-exclusion error and the unknown-key / unknown-value errors raised by `validate_filter_pairs`. Click owns this code; the orchestrator never emits it directly. |
| `3` | **UPSTREAM** — Upstream / network failure. `cfscrape` raised, HTTP error, DNS failure, request timeout. Classified by `requests.exceptions.RequestException` (cfscrape raises `requests` subclasses internally). |
| `4` | **DATA** — Data-contract / parse failure. Screener `<table>` element missing, BeautifulSoup couldn't extract a row, columns mismatch. Classified by `IndexError` / `AttributeError` / `KeyError` from inside the BS4 parsing chain. |

Classifier source-of-truth is `fincli/app/exit_codes.py`; downstream pipelines should import the constants (`SUCCESS`, `INTERNAL`, `USAGE`, `UPSTREAM`, `DATA`) rather than hardcoding integers. Spec `docs/features/archive/pipeline-mode-spec.md` §5.4.

**Output side effects**

- CSV destination resolved via the Pillar-2 precedence chain: `--output PATH` > `--output -` (stdout stream) > `FINCLI_OUTPUT_DIR=<dir>` env var (parent-dir override) > default `workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv` under CWD.
- A `OUTPUT_PATH=<value>` discovery line is **always** written to **stderr** exactly once, immediately before the process exits. `<value>` is the absolute path the CSV was written to, or the literal `-` for stdout streaming. Independent of `--quiet` and `--json-summary` so pipeline integrators can recover the destination via `tail -n1 stderr | cut -d= -f2-` even when both other flags are absent. Spec `docs/features/archive/pipeline-mode-spec.md` §5.3.3.
- When `--json-summary` is set, a single-line JSON summary (schema in §5.5) is written immediately after the `OUTPUT_PATH=` line. The summary stream is **stdout** by default and **stderr** when `--output -` claims stdout for CSV bytes; on stderr it always comes after `OUTPUT_PATH=`. Spec §5.3.4.
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
| `Ticker` | str | Excel `=HYPERLINK(...)` formula wrapping the symbol on file destinations; raw symbol under `--output -` (see canonical-column note below). | `=HYPERLINK("https://finviz.com/quote.ashx?t=AAPL", "AAPL")` (file) / `AAPL` (stdout) |
| `Company` | str | Company name | `"Apple Inc."` |
| `Sector` | str | Industry sector | `"Technology"` |
| `Industry` | str | Specific industry | `"Consumer Electronics"` |
| `Country` | str | Country of incorporation | `"USA"` |
| `Market Cap` | nullable `Float64` (empty cell for missing/unparseable) | Numeric market cap (e.g., `"1.2B"` -> `1200000000.0`). **N/A semantics:** Finviz tokens `"-"`, `"_"`, `""`, `"N/A"` (any case) and any unparseable cell coerce to `pandas.NA` and serialize as an empty CSV cell — never the literal string `"nan"`, `"<NA>"`, or `0.0`. Contract enforced by `fincli.utils.market_cap.convert_market_cap_to_numeric` per `docs/features/archive/pipeline-mode-spec.md` §5.5. | `2890000000000.0` |
| `P/E` | str | Price-to-earnings ratio (kept as string; can be `"-"`) | `"28.52"` |
| `Price` | str | Current stock price (string) | `"182.63"` |
| `Change` | str | Daily price change with `%` | `"-1.23%"` |
| `Volume` | str | Daily trading volume (comma-separated string) | `"52,436,789"` |
| `Symbol` | str | Raw ticker symbol (added by the post-parse step). **Canonical machine-readable column** for pipeline consumers — always the raw symbol regardless of `--output` mode. | `"AAPL"` |

> **Canonical column note (spec §5.6):** `Symbol` is the canonical machine-readable ticker column. `Ticker` is the human/Excel-friendly column wrapped as `=HYPERLINK(...)`. Pipeline consumers should read `Symbol`. Exception: when invoked with `--output -` (stdout streaming), the `Ticker` column is **also** the raw symbol — the formula wrap is non-Excel-friendly in that context, and `pandas.read_csv` consumers downstream would otherwise be poisoned by the `=HYPERLINK(...)` literal. Column order is preserved across modes (regression-pinned by `tests/integration/test_pipeline_ticker_carveout.py`).

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

`Config.file_path(name)` is an instance method (not a `@staticmethod`) so all three precedence tiers — explicit path, env-override directory, default — are resolved at one site. The stdout sentinel intentionally **does not** affect `file_path`'s output: the dispatch (file vs stdout) lives at the orchestrator boundary in `run_stock_screener`, so callers that hit `file_path` cannot accidentally produce a file literally named `-`. Spec: `docs/features/archive/pipeline-mode-spec.md` §5.2.

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
- `logger.set_console_stream(stream: IO[str]) -> None` — retargets the two console handlers (typing-effect + plain) to the given text-mode stream. Intended for the `--output -` stdout-streaming path (Pillar 2): callers pass `sys.stderr` so progress + banner + typing chatter does not corrupt the CSV bytes piped on stdout. Default users (no `--output -`) never call this; the construction-time default is `sys.stdout`.
- `logger.set_quiet(quiet: bool) -> None` — toggles a suppression flag on the two console handlers. When `True`, both handlers short-circuit records at INFO and DEBUG level inside `emit`; WARNING and ERROR still surface. Does **not** affect the logger level or the file handlers, so `--debug --quiet` still writes debug records to `logs/activity.log` while keeping the console quiet of informational chatter. Intended for the Pillar 3 `--quiet` flag; default users never call this and the construction-time default is `False`. Spec `docs/features/archive/pipeline-mode-spec.md` §5.3.1.

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

### 5.5 JSON summary schema (`--json-summary`)

Stable per-run output emitted by `fincli/app/main.py:run_stock_screener` when the CLI was invoked with `--json-summary`. One line, valid JSON, terminated by a single newline. Stream selection per the §1 behavior table (stdout by default; stderr under `--output -`, always after the `OUTPUT_PATH=` line on that stream).

```json
{
  "schema_version": 1,
  "exit_code": 0,
  "output_path": "/abs/path/to/file.csv",
  "row_count": 42,
  "query_url": "https://finviz.com/screener.ashx?v=111&f=fa_pe_u20,sec_energy&ft=2",
  "filters": {"fa_pe": "u20", "sec": "energy"},
  "started_at": "2026-05-16T14:32:11.123456+00:00",
  "finished_at": "2026-05-16T14:32:13.789012+00:00",
  "duration_ms": 2665
}
```

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Pinned to `1`. Bump on any breaking schema change (field removed or renamed; field semantics changed). Adding fields is non-breaking and does **not** bump the version. |
| `exit_code` | int | The same exit code the process is about to return. One of the five values in the §1 exit-codes table (`0` SUCCESS / `1` INTERNAL / `2` USAGE / `3` UPSTREAM / `4` DATA). Note that `2` (USAGE) never appears in the summary in practice — Click raises before the orchestrator reaches the summary-emission chokepoint. |
| `output_path` | str | Absolute path the CSV was written to, or the literal `"-"` for stdout streaming. |
| `row_count` | int | Number of data rows written (excludes the CSV header). `0` for empty result. |
| `query_url` | str | The exact Finviz URL fetched (post-filter-build, pre-pagination). On the `--scrape-link` path this is the supplied URL verbatim. |
| `filters` | object \| null | The `{key: value}` filter dict resolved by Pillar 1 (or interactive mode); `null` for the `--scrape-link` path because no filter resolution happened. |
| `started_at` | str | ISO-8601 timestamp in UTC captured at `run_stock_screener` entry. Always tz-aware (`+00:00` suffix). |
| `finished_at` | str | ISO-8601 timestamp in UTC captured immediately before the summary is emitted. Always >= `started_at`. |
| `duration_ms` | int | `(finished_at - started_at)` in whole milliseconds. Always >= 0. |

The schema is contract-pinned by `tests/integration/test_pipeline_summary.py`. Source-of-truth constants live in `fincli/app/main.py`: `JSON_SUMMARY_SCHEMA_VERSION` (the `1` literal) and `OUTPUT_PATH_LINE_PREFIX` (the `OUTPUT_PATH=` token).

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
    output_path: str = "",
    quiet: bool = False,
    json_summary: bool = False,
) -> None
def fetch_urls(quarry: str, page_count: int) -> list[bytes]
def aggregate_rows(pages: list[bytes]) -> list[list]
def build_data_frame(data_rows: list[list]) -> pandas.DataFrame
```

`filters` is a JSON string in the canonical flat-object shape (see §6.3). The CLI normalizes the three structured-input flag forms (`--filter`, `--filters-json`, `--filters-file`) into this single string before calling. Empty string means "interactive flow" or "use whichever other input mode is set" (`--history` / `--scrape-link`).

`output_path` overrides the default destination per the §1 / §4.1 precedence chain. Empty string falls through to `FINCLI_OUTPUT_DIR` env var (if set) or the CWD-relative `workspace_output/...` default. The literal `"-"` (`config.config.STDOUT_SENTINEL`) routes the CSV to `sys.stdout` and triggers the logger console-handler reroute to stderr (see §5.2).

`quiet` and `json_summary` are the Pillar 3 stream-discipline knobs. `quiet=True` invokes `logger.set_quiet(True)` and suppresses the CLI welcome banner (see §1 behavior table). `json_summary=True` emits a single-line JSON object matching the §5.5 schema on the stream not occupied by CSV bytes (stdout by default; stderr under `--output -`), always immediately after the `OUTPUT_PATH=` stderr discovery line. Both default to `False` for back-compat.

### 6.2 `core/configuration/configurator.py`

```python
def build_config(
    use_history: bool = False,
    filters: str = "",
    scrape_link: str = "",
    output_path: str = "",
) -> Config
```

### 6.3 `core/converters/json.py`

```python
def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]
```

**Schema (locked down 2026-05-15, commit landing Pillar 1):** the JSON literal must decode to a **flat object** whose values are all strings. The empty object `{}` is allowed (returns `()` — the no-filters case). Any other shape — top-level array, scalar, or null; nested objects, arrays, numbers, booleans, or null as values — raises `ValueError` (which the CLI translates to `click.UsageError`, exit 2). This is the same shape `filter_history.json` (§4.3) uses; one schema across the system. Single quotes in the input are normalized to double quotes for shell-friendly usage. See `docs/features/archive/pipeline-mode-spec.md` §5.1 step 3 (OQ1 resolution).

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

Carved out of `fincli/app/main.py` (commit `50f46ca`, 2026-05-15) so the parser is directly testable. See §3.1 for the full input/output contract and `docs/features/archive/pipeline-mode-spec.md` §5.5 for the design rationale.

### 6.7 `fincli/resource/params/validators.py`

```python
def validate_filter_pairs(pairs: tuple[tuple[str, str], ...]) -> None
def list_valid_filters() -> dict[str, list[str]]
```

`validate_filter_pairs` is the single chokepoint that closes the silent-drop hazard at `fincli/utils/quary_builders.py:18-22` for structured input: it raises `click.UsageError` when any pair has an unknown query_key or an unknown value_code-for-known-key. The error message names the offending token and lists up to 10 valid alternatives. Called from `core.configuration.configurator.build_config` immediately after `json_to_tuples`. The `--scrape-link` and `--history` input modes deliberately skip this validator (URL is opaque; history was previously valid by construction). The interactive picker UI is also skipped — its bounds-checked input already guarantees valid pairs.

`list_valid_filters` returns the same `{query_key: [value_code, ...]}` inventory the validator walks. Used to power the inline error-message suggestions, and reserved for a future `--help-filters` CLI flag (deferred per spec §9).

Carved out (commit landing Pillar 1, 2026-05-15) per `docs/features/archive/pipeline-mode-spec.md` §5.1 step 5.

---

## 7. Stability Policy

A change is **breaking** if it alters any of:

- A CLI option name, alias, type, or default.
- A CLI exit-code convention.
- A Finviz filter `query_key`, `value_code`, or display name (because `filter_history.json` references these by name).
- The shape of any CSV column listed in §3 (rename, drop, dtype change, column-order reorder).
- The `Config` field set in §4.1 (adding new fields with safe defaults is fine; renaming or removing is not).
- The `logger` Singleton method names in §5.1.
- Any `def` signature in §6.
- The `--json-summary` schema in §5.5 — removing or renaming a field, or changing the semantics of an existing field, bumps `schema_version`. Adding new fields is non-breaking.
- The `OUTPUT_PATH=<value>` stderr discovery-line format (§1, "Output side effects"). The literal prefix is `OUTPUT_PATH=` and the value is either the absolute path or the `-` sentinel; pipeline integrators rely on `tail -n1 stderr | cut -d= -f2-` working unchanged.

When a breaking change is unavoidable:

1. **Bump a documented version**. There is no formal SemVer release today, so until one exists, stamp the change with the date in the commit message and update `docs/FEEDBACK-LOG.md` with a `### YYYY-MM-DD — <topic>` entry summarizing what changed and why.
2. **Call it out in the commit message** — a `BREAKING:` prefix is appropriate. A future-self reading `git log` should see breakage at a glance.
3. **Update `CLAUDE.md` tech-debt section** if a migration step is required of users (e.g., delete an old `filter_history.json`, regenerate output, etc.).

Non-breaking additions (new CLI options with defaults, new CSV columns appended at the end, new Pydantic fields with defaults, new public functions in §6) need no special ceremony beyond a routine commit.
