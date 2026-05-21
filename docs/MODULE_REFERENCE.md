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
| `fincli/app/cli.py` | Click entry point. Declares all CLI options: input modes (`--history`, `--scrape-link`, `--filter`, `--filters-json`, `--filters-file`, `--list-filters`), output destination (`--output`, `-o`), stream discipline (`--quiet`, `-q`, `--json-summary`), `--debug`, and the `--json` format selector that pairs with `--list-filters`. Enforces input-mode mutual exclusion (now a 6-flag set) and normalizes the three structured-input forms into one JSON string before invoking `run_stock_screener`. The `--list-filters --json` short-circuit calls `_emit_filter_inventory()` to dump the filter inventory (schema `LIST_FILTERS_SCHEMA_VERSION = 1`) and exits 0 without running the screener pipeline — see CONTRACTS §5.6 + `docs/features/archive/list-filters-spec.md`. |
| `fincli/app/main.py` | Orchestrator. `run_stock_screener(history, debug, scrape_link, filters, output_path, quiet, json_summary)` → `fetch_urls(quarry, page_count)` → `aggregate_rows(pages)` → `build_data_frame(rows, stream_to_stdout=...)` → CSV write (file path or `sys.stdout`). Wraps the pipeline in a try/except that maps exceptions through `fincli.app.exit_codes.classify` and threads the classified code into both the JSON summary and `sys.exit`. Zero-row results write a header-only CSV (spec §5.4). |
| `fincli/app/exit_codes.py` | Pillar-4 classifier. Module-level constants `SUCCESS=0`, `INTERNAL=1`, `USAGE=2`, `UPSTREAM=3`, `DATA=4` plus `classify(exc) -> int` which maps `requests.exceptions.RequestException` -> UPSTREAM, `IndexError`/`AttributeError`/`KeyError` -> DATA, and anything else -> INTERNAL. Imported by tests as the single source of truth so a future renumbering touches one file. |
| `fincli/utils/market_cap.py` | `convert_market_cap_to_numeric(value: str | None) -> float | pandas.NA`. Carved out of `fincli/app/main.py` (commit `50f46ca`) so the parser is directly testable. Handles SI suffixes (`T`/`B`/`M`/`K`, case-insensitive), strips noise (`$`/`,`/`'`/whitespace), and coerces missing/unparseable inputs to `pandas.NA` so the column serializes as empty CSV cells (not `nan`, not `0.0`). Contract pinned in CONTRACTS §3.1. |
| `fincli/cli/cli_stock_screener.py` | Interactive filter-selection UI. The `prompt_section` helper displays each filter group (Fundamental / Descriptive / Technical) one at a time using **per-section local 1-based numbering**; the user enters comma-separated numbers for that section, or presses Enter alone to skip it. Out-of-range / non-integer input reprompts cleanly. Also owns the early-return path for structured input (when `config.filters` is preloaded by the configurator, skip the picker and build the query directly) and the `filter_history.json` writeback (every successful run that produced a non-empty filter set overwrites the file). |
| `fincli/utils/web_scraper.py` | `fetch_page_sync(url)` — makes one HTTPS request via `cfscrape` with a randomized User-Agent and 10-second timeout. Implements exponential backoff on rate-limit responses. |
| `fincli/utils/quary_builders.py` | `build_stock_screener_query(filters)` — takes the list of selected filter tuples and assembles the Finviz screener URL (`https://finviz.com/screener.ashx?v=111&f=<codes>&ft=2`). Handles pagination by appending `&r=<offset>`. Side-effect-free / logger-free (silent on the URL it constructs; the orchestrator does the user-visible log). |
| `fincli/resource/params/validators.py` | `validate_filter_pairs(pairs)` raises `click.UsageError` on unknown filter key or unknown value-for-known-key. `list_valid_filters()` returns the `{query_key: [value_code, ...]}` inventory used by the validator's helpful error messages. `list_valid_filters_with_labels()` returns the labels-included sibling shape `{query_key: {"label": str, "values": {value_code: value_label}}}` powering the `fincli --list-filters --json` inventory dump for non-Python consumers (CONTRACTS §5.6). Both walkers consume a shared private `_iter_param_entries()` generator so the param-class-introspection loop lives in one place. The labels-included shape is typed by a private `_LabelledEntry(TypedDict)` (label: str, values: dict[str, str]) — eliminates the `dict[str, dict[str, object]]` re-narrow burden on consumers. Called by `core.configuration.configurator.build_config` after `json_to_tuples` to close the silent-drop hazard at the `quary_builders` layer. |
| `fincli/resource/params/_label_format.py` | Private. `attr_to_label(attr: str) -> str` mechanically derives a display label from a Python attribute name (e.g., `"FORWARD_PE"` -> `"Forward PE"`). Preserves known acronyms (`PE`, `ROA`, `EPS`, `RSI`, ...) via a frozenset, lowercases connector words (`to`, `and`, `of`, ...) when not first, title-cases everything else. Consumed by `validators.list_valid_filters_with_labels()` only; not in the §6 importable surface. Avoiding the augmentation of params files keeps the existing two-element-list contract stable per CONTRACTS §2. Spec: `docs/features/archive/list-filters-spec.md` §5.3. |
| `fincli/stock_screening/content/stock_table.py` | Top-level HTML table extractor. Uses BeautifulSoup to locate the screener result table and extract all rows. |
| `fincli/stock_screening/parsers/stock_table.py` | Per-row HTML cell parser. Converts raw `<td>` cell text to typed Python values (strings, floats, ints). Raises `AttributeError` when the link anchor is missing — caught by the Pillar-4 classifier as a DATA-class failure. |
| `fincli/stock_screening/locators/stock_table_locators.py` | CSS / element locators for the Finviz screener table — used by both the content extractor and the per-row parser to keep selectors in one place. |
| `fincli/resource/params/fundamental_params.py` | Filter parameter definitions for Finviz fundamental filters (P/E, ROE, profit margin, debt/equity, etc.). Format: `[query_key, {value_code: display_name}]`. |
| `fincli/resource/params/descriptive_params.py` | Filter parameter definitions for Finviz descriptive filters (sector, country, market cap, exchange, etc.). Same format. |
| `fincli/resource/params/technical_params.py` | Filter parameter definitions for Finviz technical filters (RSI, SMA, performance, short float, etc.). Same format. |

### Public surface

CLI commands only. No importable API is intended for external callers.

```
fincli                                  # interactive filter selection
fincli --history                        # reuse last filter selection
fincli --debug                          # verbose logging
fincli --filter fa_pe=u20 --output -    # pipeline mode: structured input, stdout streaming
fincli --filters-file ./f.json --output ./out.csv --json-summary  # file output + JSON summary
```

Internal function signatures (for testing — full contract in CONTRACTS §6):

```python
# fincli/app/main.py
def run_stock_screener(
    history: bool = False,
    debug: bool = False,
    scrape_link: str = "",
    filters: str = "",       # canonical-shape JSON string (see core.converters.json)
    output_path: str = "",   # file path, "-" sentinel, or "" for default
    quiet: bool = False,
    json_summary: bool = False,
) -> None
    # Builds config internally via build_config(...). Wraps the pipeline in a
    # try/except that maps exceptions through `fincli.app.exit_codes.classify`
    # before calling sys.exit(<classified code>). Single chokepoint for the
    # OUTPUT_PATH=<value> stderr line + (optional) JSON summary line via
    # `_emit_run_tail`. Writes a header-only CSV on the zero-row branch so
    # every successful run produces a discoverable output.

def fetch_urls(quarry, page_count)
    # Fetches page_count pages from the Finviz query URL quarry.
def aggregate_rows(pages: list[bytes]) -> list[list]
def build_data_frame(rows: list[list], stream_to_stdout: bool = False) -> DataFrame
    # When stream_to_stdout is True, skips the Excel =HYPERLINK(...) wrap on
    # the Ticker column so pandas.read_csv consumers downstream see raw
    # symbols. Symbol column is always the raw symbol regardless. Spec §5.6.

# fincli/app/exit_codes.py
SUCCESS = 0; INTERNAL = 1; USAGE = 2; UPSTREAM = 3; DATA = 4
def classify(exc: BaseException) -> int

# fincli/utils/market_cap.py
def convert_market_cap_to_numeric(value: str | None) -> float | pandas.NA
```

### Data shapes

Output `DataFrame` columns — full schema in CONTRACTS §3.1. Highlights:

| Column | Type | Notes |
|--------|------|-------|
| `Symbol` | `str` | **Canonical machine-readable ticker** — always raw symbol regardless of `--output` mode |
| `Ticker` | `str` | `=HYPERLINK(...)` Excel formula for file destinations; raw symbol under `--output -` (spec §5.6) |
| `Market Cap` | nullable `Float64` | Coerced from Finviz `"1.2B"` style via `convert_market_cap_to_numeric`; missing/unparseable -> `pandas.NA` -> empty CSV cell |
| `Company`, `Sector`, `Industry`, `Country` | `str` | Direct from Finviz |
| `P/E`, `Price`, `Change`, `Volume` | `str` | Kept as strings (can be `"-"` or comma-separated) |
| `No.` | `str` | Finviz row number |

Filter history saved as `<Config.history_dir>/filter_history.json`. The directory comes from `Config.history_dir` (default: platformdirs `user_data_dir("fincli", appauthor=False) / "local_history"`; overrideable via `HISTORY_DIR` env var read in `build_config`). See `CONTRACTS.md` §4.1 for the full contract.

CSV destination resolved via the Pillar-2 precedence chain: `--output PATH` > `--output -` (stdout stream) > `FINCLI_OUTPUT_DIR` env (parent-dir override) > default `workspace_output/stock_screener_{YYYY-MM-DD_HH-MM}.csv`.

Pipeline mode adds two side-effect outputs the orchestrator surfaces on every run:

- `OUTPUT_PATH=<value>` line written to stderr immediately before exit (absolute path, or `-` for stdout streaming, or empty when an exception fired before the destination was resolved).
- If `--json-summary` is set, a single-line JSON object (schema in CONTRACTS §5.5) written to stdout by default (stderr under `--output -`).

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
| `core/configuration/config_base.py` | `SystemSettings(BaseModel)` — Pydantic base class for all app configs. `Configurable[S]` generic protocol (reserved for future extension; `build_config` returns concrete `Config` today). |
| `core/configuration/configurator.py` | `build_config(use_history, filters, scrape_link, output_path)` — constructs and returns a `Config` instance. Reads `HISTORY_DIR` and `FINCLI_OUTPUT_DIR` env vars. When `filters` is non-empty, parses the JSON via `json_to_tuples` and validates against the Finviz inventory via `fincli.resource.params.validators.validate_filter_pairs` (unknown key/value -> `click.UsageError` -> exit 2). |
| `core/converters/json.py` | `json_to_tuples(json_str)` — parses a flat-object JSON string into a tuple of `(key, value)` pairs. **Schema locked down (spec §5.1 step 3):** only flat object `{"fa_pe":"u20"}` is accepted; list shape, nested objects, non-string values all raise `ValueError`. The CLI translates the `ValueError` into a `click.UsageError` (exit 2). |

### Public surface

```python
# core/configuration/configurator.py
def build_config(
    use_history: bool = False,
    filters: str = "",        # canonical-shape JSON string
    scrape_link: str = "",
    output_path: str = "",    # exact path, "-" sentinel, or "" for default
) -> Config

# core/converters/json.py
def json_to_tuples(filters_json: str) -> tuple[tuple[str, str], ...]
    # raises ValueError on non-dict shape, nested object, or non-string value
```

### Data shapes

- `Config` fields are validated by Pydantic on construction. Any invalid type raises `pydantic.ValidationError` before execution reaches the CLI body.
- `filter_history.json` is a flat JSON object mapping `query_key` -> `value_code`: `{"fa_pe":"u20","sec":"energy"}`. Written by `select_filters_and_values` on every successful run that produced a non-empty filter set; read by `build_config` when `--history` is set.
- `json_to_tuples` input: a flat-object JSON string like `{"fa_pe":"u20","sec":"energy"}`. Output: `(("fa_pe", "u20"), ("sec", "energy"))` (insertion order preserved).

### Error modes

| Condition | Behavior |
|-----------|----------|
| Invalid config field type | `pydantic.ValidationError` raised at startup; CLI exits with error message. |
| `filter_history.json` missing when `--history` is set | `build_config` raises `FileNotFoundError`; the user re-runs without the flag for interactive selection. |
| Malformed filter JSON string | `json_to_tuples` raises `ValueError` (a `JSONDecodeError` subclass for malformed JSON, or a fresh `ValueError` for non-canonical shape). CLI translates to `click.UsageError` (exit 2). |
| Unknown filter key/value | `validate_filter_pairs` raises `click.UsageError` (exit 2) with a helpful message listing valid alternatives. |

### Integration

- **Consumed by** `fincli/app/cli.py` at startup via `build_config`.
- **Extended by** `config/config.py` which defines the concrete `Config` class.
- **No external dependencies** — plain Pydantic, `json`, `os`. This is intentional to keep the framework portable.

---

## `config/`

### Purpose

Project-level Pydantic settings. Defines the concrete `Config` class that the screener instantiates. Extends `SystemSettings` with the `file_path(name)` helper that resolves the CSV destination through the Pillar-2 precedence chain (spec §5.2).

### Key files

| File | Role |
|------|------|
| `config/config.py` | `Config(SystemSettings)` — defines `use_history`, `filters`, `scrape_link`, `history_dir`, `output_path`, `output_dir` fields and the `file_path(name)` instance method. Exports `STDOUT_SENTINEL = "-"` for the stdout-streaming dispatch site. |

### Public surface

```python
# config/config.py
STDOUT_SENTINEL = "-"

class Config(SystemSettings):
    use_history: bool = False
    filters: tuple = ()
    scrape_link: str = ""
    history_dir: Path = ...        # platformdirs default
    output_path: str = ""          # --output PATH or - sentinel
    output_dir: Path | None = None # FINCLI_OUTPUT_DIR env override

    def file_path(self, name: str) -> str:
        # Precedence: output_path > output_dir > default
        # Returns the resolved CSV path (timestamped for the default and
        # env-override tiers; verbatim under output_path).
```

`file_path` is an instance method (not `@staticmethod`) so all three precedence tiers resolve from one site. The stdout sentinel intentionally does **not** affect `file_path`'s output — the dispatch (file vs stdout) lives at the orchestrator boundary so callers can't accidentally produce a file literally named `-`.

### Data shapes

- `Config` inherits all fields from `SystemSettings` plus the screener-specific fields above.
- Default `file_path` output is `<CWD>/workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv`.
- With `output_dir` set: `<output_dir>/{name}_{YYYY-MM-DD_HH-MM}.csv` (timestamped basename preserved).
- With `output_path` set to a path: that path verbatim (no timestamp).
- With `output_path == "-"`: the dispatch lives elsewhere; `file_path` falls through to the default tier.

### Error modes

| Condition | Behavior |
|-----------|----------|
| `workspace_output/` does not exist | Pandas creates the parent dir on `to_csv`; existence not enforced by `file_path`. |
| `--output PATH` parent directory does not exist | Click validates via `click.Path(dir_okay=False, writable=True)` at parse time. |
| Invalid `SystemSettings` field at instantiation | `pydantic.ValidationError` propagated to caller. |

### Integration

- **Instantiated by** `core/configuration/configurator.py` via `build_config`.
- **`STDOUT_SENTINEL` constant** imported by `fincli/app/cli.py` (banner-suppression gate) and `fincli/app/main.py` (CSV dispatch + logger reroute).
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
logger.warn("message")                    # note: `.warn` not `.warning`
logger.error("title", message="...")      # parameter order is flipped (footgun)
logger.debug("message")
logger.set_level(logging.DEBUG)
logger.set_console_stream(sys.stderr)     # Pillar 2 — used by --output - mode
logger.set_quiet(True)                    # Pillar 3 — suppress INFO/DEBUG console
```

Handlers are not part of the public surface — they are initialized internally and must not be instantiated directly. The `set_console_stream` and `set_quiet` methods exist so the orchestrator has named entry points for the Pillar-2 / Pillar-3 stream-discipline behavior; default users never call them.

**Footgun:** `logger.error(title, message="")` has its parameter order **flipped** relative to the other methods. `logger.debug/info/warn(message, title="")` puts message first, but `logger.error(title, message="")` puts title first. Any new caller should use the documented order; the inconsistency is pre-existing and out of scope to fix.

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

*Last updated: 2026-05-21 (list-filters-spec shipped: new `fincli.resource.params._label_format` private module, extended `fincli.resource.params.validators` with `list_valid_filters_with_labels` + shared `_iter_param_entries` walker, extended `fincli.app.cli` with `--list-filters --json` short-circuit + `LIST_FILTERS_SCHEMA_VERSION = 1`). Prior milestone 2026-05-16 (pipeline-mode shipped: new `fincli.app.exit_codes` module, `fincli.utils.market_cap` carve-out, `fincli.resource.params.validators`, updated `fincli.app.main` / `core.configuration.configurator` / `core.converters.json` / `config.config` / `logger.logger` surfaces). Maintained alongside source changes — update this file whenever a module's public surface, key files, or error modes change.*
