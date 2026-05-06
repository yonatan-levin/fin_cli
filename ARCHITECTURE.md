# ARCHITECTURE.md - Fin CLI System Architecture

This document is the source of truth for Fin CLI's system architecture.

## System Overview

**Fin CLI** is a single-mode Python command-line application that screens stocks from Finviz.com. It is built as one importable package (`fincli`) with a Click entry point under `app/`, plus a small set of shared cross-cutting packages (`core`, `config`, `logger`). There is no server, no database, no network listener — outputs land as timestamped CSVs in `workspace_output/`.

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
                    +-------------+-------------+
                                  |
                                  v
                    +---------------------------+
                    |    Orchestration Layer    |
                    |    fincli/app/main.py     |
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

## Module Map

| Module | Purpose | Key Files |
|---|---|---|
| `fincli/` | Stock screener — builds a Finviz query URL, fetches all paginated pages, parses the HTML stock table, writes CSV. | `fincli/app/cli.py`, `fincli/app/main.py`, `fincli/cli/cli_stock_screener.py` (section-by-section filter UI via `prompt_section`), `fincli/utils/web_scraper.py`, `fincli/utils/quary_builders.py`, `fincli/stock_screening/{content,parsers,locators}/stock_table*.py`, `fincli/resource/params/` |
| `core/` | Pure Python configuration framework — Pydantic base classes (`SystemSettings`), JSON-to-tuple conversion, Configurator builder. Has no external service dependencies. | `core/configuration/config_base.py`, `core/configuration/configurator.py`, `core/converters/json.py` |
| `config/` | Concrete `Config` instance for the application — extends `SystemSettings`, exposes `use_history`, `filters`, `scrape_link`, and `file_path(name)` for timestamped CSV destinations. | `config/config.py` |
| `logger/` | Singleton logger with three named handlers: a typing-effect console handler, plain console handler, and a JSON file handler. Imported as `from logger import logger`. | `logger/logger.py`, `logger/handlers/`, `logger/formatters/` |

Supporting (not part of the active runtime path):

| Module | Status |
|---|---|
| `scripts/` | Dependency-checking utilities. |
| `tests/` | Folder layout exists (`tests/unit`, `tests/domain`, `tests/e2e`); test bodies will land in Phase 2 (see `CLAUDE.md`). |

## Data Flow

```
[1] Click CLI                       fincli/app/cli.py
       |   --history / --debug
       v
[2] Config build                    core/configuration/configurator.py
       |   loads filter_history.json when --history is set
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
       |   normalizes Market Cap "1.2B" -> 1_200_000_000,
       |   wraps Ticker in =HYPERLINK() for Excel
       v
[8] CSV write                        Config.file_path("stock_screener")
       |   workspace_output/stock_screener_YYYY-MM-DD_HH-MM.csv
       v
       (done)
```

## Layering

```
+------------------------------------------------------------+
|                     Click CLI Layer                        |
|   fincli/app/cli.py                                        |
|   (option parsing, --help text, logger level toggling)     |
+------------------------------------------------------------+
|                    Orchestration Layer                     |
|   fincli/app/main.py                                       |
|   (pipeline composition: build query -> fetch -> parse     |
|    -> DataFrame -> write CSV)                              |
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

## Folder Structure

```
fin_cli/
  fincli/                      # Stock screener
    app/
      cli.py                   # Click entry point
      main.py                  # Pipeline orchestrator
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
    THESIS.md
    MODULE_REFERENCE.md
    FEEDBACK-LOG.md
    bugs/, refactoring/, reviewer/
    superpowers/specs/

  agents/                      # AI-agent rules + role files
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
  AGENTS.md

  pyproject.toml
  requirements.txt
  run.sh / run.bat             # Convenience launchers
  singleton.py                 # Standalone metaclass utility
```

## Threading Model

The screener pipeline is fully synchronous. Pages from Finviz are fetched one at a time. This is intentional — the scraper cooperates with Finviz's anti-bot pacing by not flooding the host.

The Singleton `Logger` is constructed once at import time. Its underlying `logging.Logger` handlers are Python's stdlib `logging` handlers, which are thread-safe by design. The typing-animation console handler serializes its writes to stdout under the same lock, so any future fan-out work (none today) would be safe to log freely.

There is no `asyncio` and no `ThreadPoolExecutor` in the active runtime path. Adding async I/O is on the long-term roadmap (`docs/THESIS.md`) but not in active scope.

## Configuration Shape

```
core/configuration/config_base.py
    SystemConfiguration (Pydantic BaseSettings; .env file support)
    SystemSettings        (BaseModel; base for all app configs)
    Configurable[S]        (generic interface for "I produce a config of type S")

core/configuration/configurator.py
    build_config(use_history: bool = False, filters: str = "") -> Config
        - if use_history: read fincli/local_history/filter_history.json
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
