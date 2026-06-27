# ARCHITECTURE.md - Fin CLI System Architecture

This document is the source of truth for Fin CLI's system architecture.

## System Overview

**Fin CLI** is a Python package that screens stocks from Finviz.com through two co-equal entry points: a CLI (`fincli/`) and an HTTP API (`fincli_api/`). Both consume the same orchestrator (`fincli.app.main.screen_to_dataframe`) and the same filter inventory (`fincli.resource.params.validators.list_valid_filters_with_labels`), so the contract cannot drift across surfaces. There is no database; CLI outputs land as timestamped CSVs in `workspace_output/` by default (or wherever pipeline-mode flags redirect), and HTTP API outputs are typed JSON envelopes returned per-request.

The CLI has two usage shapes that share the same orchestrator:

1. **Interactive** — bare `fincli` prompts the user through the three-section filter picker, writes a timestamped CSV under `workspace_output/`. The historical shape; unchanged.
2. **Pipeline** — `fincli --filter/--filters-json/--filters-file ... --output PATH-or-` is consumable by another program. Reads structured input, writes to an exact destination (or streams CSV on stdout), emits a `OUTPUT_PATH=<value>` discovery line on stderr, optionally emits a single-line JSON summary, and exits with one of five classified codes (0/1/2/3/4 — see CONTRACTS §1 exit-codes table).

The HTTP API exposes three first-class endpoints (`GET /filters`, `POST /screens`, `GET /healthz`) via FastAPI, with the contract pinned by a committed OpenAPI 3.1.0 snapshot at `docs/api/openapi.{yaml,json}`. Polyglot consumers codegen typed clients from the snapshot. See CONTRACTS §8 + `docs/api/openapi.yaml` for the wire contract; `fincli_api/` for the package; `INTEGRATION.md` "HTTP API mode" for the consumer-facing guide.

```
   +---------------------------+        +---------------------------+
   |        End User           |        |    Polyglot Consumer      |
   | (terminal / shell / CI)   |        |   (Go / TS / Rust / ...)  |
   +-------------+-------------+        +-------------+-------------+
                 |                                    |
                 v                                    v
   +---------------------------+        +---------------------------+
   |      Click CLI Layer      |        |    FastAPI Layer          |
   |  fincli/app/cli.py        |        |    fincli_api/main.py     |
   |                           |        |    + routes/* + handlers  |
   +-------------+-------------+        +-------------+-------------+
                 |                                    |
                 |                                    v
                 |                      +---------------------------+
                 |                      |   Adapter (boundary)      |
                 |                      | fincli_api/adapters/      |
                 |                      |   fincli.py               |
                 |                      +-------------+-------------+
                 |                                    |
                 +------------+ same orchestrator +---+
                              v
                +---------------------------+
                |    Orchestration Layer    |
                |  fincli/app/main.py       |
                |  screen_to_dataframe()    |
                +-------------+-------------+
                              |
                              v
                +---------------------------+
                |   Screener pipeline       |
                |   (Finviz HTML scrape)    |
                |   cfscrape + BS4          |
                +-------------+-------------+
                              |
                              v
                  Finviz.com (Cloudflare-protected HTML)
```

**Adapter-boundary rule (spec §3.2):** `fincli_api/adapters/fincli.py` is the ONLY file in `fincli_api/` allowed to import from `fincli/`. Every other API module imports through the adapter. This isolates the API package from fincli internals and makes the contract enforceable mechanically.

## Module Map

| Module | Purpose | Key Files |
|---|---|---|
| `fincli/` | Stock screener — builds a Finviz query URL, fetches all paginated pages, parses the HTML stock table, writes CSV or returns a DataFrame. | `fincli/app/cli.py`, `fincli/app/main.py` (`screen_to_dataframe`, `run_stock_screener`), `fincli/cli/cli_stock_screener.py` (section-by-section filter UI via `prompt_section`), `fincli/utils/web_scraper.py`, `fincli/utils/quary_builders.py`, `fincli/stock_screening/{content,parsers,locators}/stock_table*.py`, `fincli/resource/params/`, `fincli/app/exit_codes.py` (classifier shared with HTTP API exception handler) |
| `fincli_api/` | FastAPI HTTP service exposing the screener over REST+JSON. Adapter-boundary rule: only `adapters/fincli.py` may import from `fincli/`. | `fincli_api/main.py` (FastAPI app + uvicorn entry), `fincli_api/config.py` (`ApiConfig` via pydantic-settings), `fincli_api/routes/{filters,screens,meta}.py`, `fincli_api/adapters/fincli.py` (boundary), `fincli_api/models/{filters,screens,errors}.py` (Pydantic shapes), `fincli_api/exception_handlers.py` (classifier-driven envelope) |
| `core/` | Pure Python configuration framework — Pydantic base classes (`SystemSettings`), JSON-to-tuple conversion, Configurator builder. Has no external service dependencies. | `core/configuration/config_base.py`, `core/configuration/configurator.py`, `core/converters/json.py` |
| `config/` | Concrete `Config` instance for the application — extends `SystemSettings`, exposes `use_history`, `filters`, `scrape_link`, and `file_path(name)` for timestamped CSV destinations. | `config/config.py` |
| `logger/` | Singleton logger with three named handlers: a typing-effect console handler, plain console handler, and a JSON file handler. Imported as `from logger import logger`. | `logger/logger.py`, `logger/handlers/`, `logger/formatters/` |

Supporting:

| Module | Status |
|---|---|
| `scripts/` | Dev tooling: `scripts/dump_openapi.py` regenerates `docs/api/openapi.{yaml,json}` from the FastAPI app (with `--check` mode for drift detection). |
| `tests/` | Three-tier pyramid in active use: `tests/unit/` (mocked adapters), `tests/integration/` (real fincli + mocked Finviz HTML), `tests/e2e/` (live Finviz, opt-in via `pytest -m live`). `tests/unit/api/`, `tests/integration/api/`, `tests/e2e/api/` mirror the same tiers for `fincli_api/`. |

## Data Flow

```
[1] Click CLI                       fincli/app/cli.py
       |   Input-mode flags (mutually exclusive):
       |     --history / --scrape-link <url> / --filter k=v
       |     / --filters-json '<json>' / --filters-file <path>
       |   Output-destination flags (orthogonal):
       |     --output PATH / --output - / FINCLI_OUTPUT_DIR env
       |   Stream-discipline flags: --quiet, --json-summary, --debug
       v
[2] Config build                    core/configuration/configurator.py
       |   loads filter_history.json when --history is set;
       |   normalizes structured input through json_to_tuples and
       |   validates against the filter inventory (raises UsageError
       |   on unknown key/value -> exit 2);
       |   reads FINCLI_OUTPUT_DIR + HISTORY_DIR env vars.
       v
[3] Interactive filter selection    fincli/cli/cli_stock_screener.py
       |   each section (Fundamental / Descriptive / Technical) is shown
       |   in turn with per-section 1-based local numbering; user types
       |   comma-separated numbers for that section (or presses Enter to
       |   skip); out-of-range / non-integer input reprompts cleanly.
       v
[4] Query URL construction          fincli/utils/quary_builders.py
       |   -> https://finviz.com/screener.ashx?v=111&f=<codes>&ft=2&r=<offset>
       v
[5] HTTP fetch (Cloudflare bypass)  fincli/utils/web_scraper.py
       |   cfscrape.create_scraper() with randomized User-Agent, 10s timeout
       v
[6] HTML table parsing              fincli/stock_screening/content/stock_table.py
       |   BeautifulSoup over table.styled-table-new; reads page count,
       |   then iterates r=1, r=21, r=41, ... until exhausted
       v
[7] Row aggregation + DataFrame     fincli/app/main.py: aggregate_rows,
                                    build_data_frame
       |   normalizes Market Cap "1.2B" -> 1_200_000_000 (nullable Float64;
       |     unparseable cells coerce to pandas.NA via
       |     fincli.utils.market_cap.convert_market_cap_to_numeric);
       |   wraps Ticker in =HYPERLINK() for Excel — EXCEPT under
       |     --output - where the raw symbol is preserved so
       |     pandas.read_csv consumers downstream are not poisoned;
       |   Symbol column is the canonical machine-readable ticker.
       v
[8] CSV write                       file destination OR sys.stdout
       |   destination precedence (Pillar 2):
       |     --output PATH > --output - > FINCLI_OUTPUT_DIR > default
       |   zero-row results write a header-only CSV (Pillar 4 §5.4 —
       |     "every successful run produces a discoverable output").
       v
[9] Trailing emission chokepoint    fincli/app/main.py: _emit_run_tail
       |   OUTPUT_PATH=<value> line to stderr (always),
       |   single-line JSON summary if --json-summary (stream depends on
       |   --output: stdout by default, stderr under --output -).
       v
[10] Classified exit               fincli/app/exit_codes.classify
       |   sys.exit(SUCCESS|INTERNAL|UPSTREAM|DATA) — Click owns USAGE.
       v
       (done)
```

## Layering

```
+------------------------------------------------------------+
|        Click CLI Layer       |       FastAPI Layer         |
|  fincli/app/cli.py           |  fincli_api/main.py         |
|  (option parsing, --help,    |  (FastAPI app + routes/* +  |
|   logger level toggling)     |   exception_handlers.py)    |
+------------------------------+-----------------------------+
|                          |                                 |
|                          v                                 |
|                  +------------------------+                |
|                  |  Adapter (boundary)    |                |
|                  | fincli_api/adapters/   |                |
|                  |   fincli.py            |                |
|                  +-----------+------------+                |
|                              |                             |
+------------------------------+-----------------------------+
|                    Orchestration Layer                     |
|   fincli/app/main.py                                       |
|   (pipeline composition: build query -> fetch -> parse     |
|    -> DataFrame -> write CSV / return to caller)           |
+------------------------------------------------------------+
|                Domain / UI Layer                           |
|   fincli/cli/cli_stock_screener.py       (filter UI)       |
+------------------------------------------------------------+
|                  Utility / I/O Layer                       |
|   fincli/utils/web_scraper.py       (HTTP via cfscrape)    |
|   fincli/utils/quary_builders.py    (URL construction)     |
|   fincli/stock_screening/           (BeautifulSoup parser) |
+------------------------------------------------------------+
|                  Cross-cutting                             |
|   config/config.py                                         |
|   core/configuration/                                      |
|   logger/                                                  |
+------------------------------------------------------------+
```

**Layering rule:** orchestration calls down into the filter UI and utility/I/O, never the reverse. Utility/I/O modules receive primitive inputs (a URL, raw HTML bytes) and have no awareness of how they will be assembled into a DataFrame. Cross-cutting modules are imported anywhere they are needed.

**Adapter-boundary rule (spec §3.2):** the FastAPI layer imports ONLY through `fincli_api/adapters/fincli.py`. Routes / models / exception handlers in `fincli_api/` may NOT `import fincli.<anything>` directly. This isolates the API package from fincli internals so the contract surface is enforceable via a single file's diff.

There is no formal dependency-injection container. Wiring is done by direct import and function call in the orchestration layer. The Singleton logger is the only globally-visible runtime object.

### Side effects

Every successful run produces three observable side effects beyond the CSV write itself; pipeline integrators rely on this trio to discover the result without screen-scraping log lines:

1. **`OUTPUT_PATH=<value>` discovery line** — written to **stderr** exactly once, immediately before exit, on every run (regardless of success/failure or any other flag). `<value>` is either the absolute path the CSV was written to, or the literal `-` sentinel for `--output -` streaming. The destination is resolved before the orchestrator's try-block opens, so the line is populated on every exit code (0/1/3/4) for any `--output PATH` invocation — never empty. Format pinned by CONTRACTS §1 + §7.
2. **`--json-summary` line** (optional) — when `--json-summary` is set, a single-line JSON object matching the schema in CONTRACTS §5.5 is written immediately after the `OUTPUT_PATH=` line. Routes to **stdout** by default and to **stderr** when `--output -` claims stdout for CSV bytes.
3. **Exit code** — one of five classified values (CONTRACTS §1 exit-codes table). `0` SUCCESS / `1` INTERNAL / `2` USAGE (Click) / `3` UPSTREAM / `4` DATA. The orchestrator's try/except wrapper around the pipeline runs every uncaught exception through `fincli.app.exit_codes.classify` before threading the code into both the JSON summary and `sys.exit`.

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

## Folder Structure

```
fin_cli/
  fincli/                      # Stock screener CLI
    app/
      cli.py                   # Click entry point
      main.py                  # Pipeline orchestrator + screen_to_dataframe helper
      exit_codes.py            # classify() — single source of truth for failure
                               #             classification (CLI + HTTP API consume it)
    cli/
      cli_stock_screener.py    # Section-by-section interactive filter UI
    resource/
      params/
        fundamental_params.py
        descriptive_params.py
        technical_params.py
        const.py
    stock_screening/
      content/
        stock_table.py         # HTML table extractor
      parsers/
        stock_table.py         # row -> dict parser
      locators/
        stock_table_locators.py  # CSS / element locators
    utils/
      web_scraper.py           # cfscrape wrapper
      quary_builders.py        # Finviz URL construction
      user_agent_rotator.py

  fincli_api/                  # HTTP API (FastAPI) — sibling of fincli/
    main.py                    # FastAPI app + uvicorn entry (bound to fincli-api script)
    config.py                  # ApiConfig via pydantic-settings (host/port/log_level)
    routes/
      filters.py               # GET /filters
      screens.py               # POST /screens (with validate_filter_pairs gate)
      meta.py                  # GET /healthz
    adapters/
      fincli.py                # Boundary layer — only file allowed to import from fincli/
    models/
      filters.py               # FilterInventory + FilterEntry
      screens.py               # ScreenRequest + ScreenResult + Stock
      errors.py                # ErrorResponse (Literal discriminator on error_class)
    exception_handlers.py      # register_exception_handlers(app) via exit_codes.classify

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

  tests/                       # 3-tier pyramid (live tier opt-in via -m live)
    unit/
      api/                     # FastAPI TestClient + mocked adapter
      ...                      # mocked-dep tests for fincli/
    integration/
      api/                     # TestClient + real fincli + mocked Finviz HTML
      fixtures/                # 5 Finviz HTML fixtures (happy/one_page/empty/no_table/malformed_row)
    e2e/
      api/                     # TestClient + live Finviz (3 tests, @pytest.mark.live)

  scripts/
    dump_openapi.py            # Regenerate docs/api/openapi.{yaml,json} (with --check)

  workspace_output/            # CSV results (gitignored)
  workspace_materials/         # Working notes (gitignored)
  logs/                        # activity.log + error.log (gitignored)

  docs/                        # Project documentation
    THESIS.md
    MODULE_REFERENCE.md
    FEEDBACK-LOG.md
    api/                       # Committed OpenAPI 3.1.0 snapshot
      openapi.yaml
      openapi.json
    bugs/, refactoring/, reviewer/
    features/                  # Feature specs (archive/ = shipped)
    superpowers/specs/         # Brainstorming-derived design specs (archive/ = shipped)

  agents/                      # AI-agent rules + role files
    rules/
    roles/

  .claude/                     # Claude Code harness configuration
    settings.json
    settings.local.json
    hooks/                     # SessionStart / PreToolUse / PostToolUse / Stop

  ARCHITECTURE.md              # this file
  CLAUDE.md
  CONTRACTS.md                 # §1 CLI surface; §8 HTTP API surface
  INTEGRATION.md               # Polyglot-consumer guide (CLI mode + HTTP API mode)
  README.md
  TESTING.md
  TOOLS_REFERENCE.md
  AGENTS.md

  pyproject.toml
  pytest.ini                   # Canonical pytest config (pytest.ini > pyproject)
  requirements.txt
  singleton.py                 # Standalone metaclass utility
```

## Threading Model

The screener pipeline is fully synchronous. Pages from Finviz are fetched one at a time. This is intentional — the scraper cooperates with Finviz's anti-bot pacing by not flooding the host.

The Singleton `Logger` is constructed once at import time. Its underlying `logging.Logger` handlers are Python's stdlib `logging` handlers, which are thread-safe by design. The typing-animation console handler serializes its writes to stdout under the same lock, so any future fan-out work (none today) would be safe to log freely.

The HTTP API's route handlers are sync (`def`, not `async def`) — fincli is fully sync, so FastAPI runs the handlers in its default thread pool. At single-user load (the spec's scope), the thread pool is fine; the bottleneck is Finviz's per-IP rate ceiling, not concurrency. No `asyncio` is used in `fincli_api/` either. Adding true async I/O would require porting the scraper off cfscrape and is on the long-term roadmap (`docs/THESIS.md`) but not in active scope.

## Configuration Shape

```
core/configuration/config_base.py
    SystemConfiguration (Pydantic BaseSettings; .env file support)
    SystemSettings        (BaseModel; base for all app configs)
    Configurable[S]        (generic interface for "I produce a config of type S")

core/configuration/configurator.py
    build_config(
        use_history: bool = False,
        filters: str = "",
        scrape_link: str = "",
        output_path: str = "",
    ) -> Config
        - if use_history: read <Config.history_dir>/filter_history.json
        - if filters:     parse JSON string -> tuple of (key, value) pairs,
                          validate against the Finviz filter inventory
        - if scrape_link: populate Config.scrape_link (direct-URL bypass)
        - if output_path: populate Config.output_path (Pillar-2 destination pin)
        - reads HISTORY_DIR + FINCLI_OUTPUT_DIR env vars from os.getenv
        - else:           empty Config (interactive selection will populate later)

config/config.py
    class Config(SystemSettings):
        name:        str  = "Stock Screener CLI config"
        description: str  = "Configuration for the Stock Screener CLI app."
        use_history: bool = False
        filters:     tuple = ()
        scrape_link: str  = ""
        history_dir: Path  = platformdirs.user_data_dir("fincli") / "local_history"
        output_path: str   = ""            # --output PATH or - sentinel
        output_dir:  Path | None = None    # FINCLI_OUTPUT_DIR env override

        def file_path(self, name: str) -> str:
            # Pillar 2 precedence:
            #   output_path > output_dir > workspace_output/ default
            # Returns the resolved CSV path (timestamped for the default
            # and env-override tiers; verbatim under output_path).
```

The configuration object is constructed once per CLI invocation and threaded through `main.py` by direct argument passing. There is no global config singleton; the only global state is the logger.

When `--history` is set, the most recent filter selection is replayed verbatim — useful for re-running the same screen on a fresh trading day. The history file is plain JSON of `{filter_key: value_code}` pairs, written by the interactive filter UI on each successful run.

## Design Patterns

| Pattern | Where | Purpose |
|---|---|---|
| Singleton (metaclass) | `singleton.py` -> `logger/logger.py` | One process-wide logger instance |
| Builder | `core/configuration/configurator.build_config()` | Produce a `Config` from many possible sources (interactive, history, JSON) |
| Strategy (data) | `fincli/resource/params/*.py` | Each filter category is a pluggable `[query_key, {value_code: display_name}]` dict |
| Template | `fincli/app/cli.py` | Click `@click.group(invoke_without_command=True)` so `python -m fincli` with no subcommand executes the default flow |

## Performance & Resource Notes

- **Screening** is dominated by sequential HTTP latency (~0.5–2 s per Finviz page; Cloudflare adds variance).
- **Memory** stays modest: each parsed page yields a few KB of row data; the combined DataFrame written to CSV is the largest object in memory and is dominated by row count, not column complexity.
- **Failure on a single page does not necessarily abort the run** — the scraper logs the error and the surrounding loop decides whether to continue based on whether subsequent pages parse cleanly.
