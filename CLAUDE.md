# CLAUDE.md - Fin CLI

This file provides guidance for AI assistants (Claude, etc.) working on this codebase.

READING `AGENTS.md` IS MANDATORY. (`AGENTS.md` lands in the final commit of the agent-harness rollout — Phase 1 of `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`. If it does not yet exist on this branch, treat the spec as the authoritative index until it does.)

## Project Overview

**Fin CLI** is a Python command-line application for stock screening and fundamental analysis. It has two operating modes:

1. **`fincli`** — interactive Finviz.com stock screener. The user picks filter values from the standard Finviz vocabulary (P/E, sector, country, RSI, etc.); the tool builds the corresponding Finviz URL, fetches every paginated result page through `cfscrape` (Cloudflare-bypassing HTTPS client), parses the HTML stock table with BeautifulSoup, and writes the result to a timestamped CSV.

2. **`fundainsight`** — fundamental-analysis pipeline that runs the screener, then for each candidate ticker fetches quarterly balance sheet, market cap, and 30-day price history from Yahoo Finance via `yahooquery`. It computes price-to-asset and price-to-current-asset ratios, applies country/sector/price filters, and writes the result to a second timestamped CSV. The intent is to surface stocks trading below their adjusted book value of current assets.

- **Language / runtime**: Python 3.12+
- **Packaging**: `pyproject.toml` (PEP 621); editable install via `pip install -e ".[dev]"`
- **Distribution**: source-only; no PyPI release at this time
- **Stack**: Click (CLI), pandas (data), yahooquery (Yahoo Finance), cfscrape (Cloudflare bypass), BeautifulSoup4 (HTML parsing), Pydantic (config validation), colorama (ANSI colors)

## Build & Run

```bash
# Install the project + dev tooling in editable mode
pip install -e ".[dev]"

# Run the screener mode
python -m fincli                # interactive
python -m fincli --history      # reuse last filter selection
python -m fincli --debug        # verbose logging

# Run the fundamental-analysis mode
python -m fundainsight --history
python -m fundainsight --set-filters '<json>'
python -m fundainsight --scrape-link 'https://finviz.com/screener.ashx?...'
python -m fundainsight --debug

# Or use the convenience launchers
./run.sh                        # Linux / macOS — interactive menu
run.bat                         # Windows

# Tests (Phase 2 work — bodies not yet present; structure exists)
pytest tests/
pytest tests/unit/
pytest tests/domain/
pytest tests/e2e/

# Lint + format (Ruff)
ruff check .
ruff check --fix .
ruff format .
ruff format --check .

# Type-check (mypy strict)
mypy fundainsight fincli core config logger
mypy --no-incremental         # bypass cache when diagnosing weirdness

# Vulnerability audit (when pip-audit is on PATH; gracefully skipped otherwise)
pip-audit -r requirements.txt
```

`workspace_output/` accumulates CSVs from each run. It is `.gitignore`d.

## Architecture

Two-mode CLI with shared configuration and logger plumbing. Layers:

```
Click CLI  ->  Orchestration (app/main.py, picker.py)
            ->  Calculators / Filters / Filter UI
            ->  Web scraper, BeautifulSoup parser, yahooquery wrapper
            ->  External services (Finviz HTML, Yahoo Finance JSON)
```

There is no DI container, no server, no database. Wiring is by direct import. The Singleton logger is the only globally-visible runtime object. Threading is synchronous in `fincli` and parallel via `ThreadPoolExecutor` in `fundainsight` for the Yahoo enrichment step.

Full diagram + per-section detail in `ARCHITECTURE.md`.

## Important Files

| File | Purpose |
|---|---|
| `fincli/app/cli.py` | Click entry point for screener mode |
| `fincli/app/main.py` | Screener pipeline orchestrator (`run_stock_screener`, `fetch_urls`, `aggregate_rows`, `build_data_frame`, `convert_market_cap_to_numeric`) |
| `fincli/cli/cli_stock_screener.py` | Interactive filter-selection UI |
| `fincli/utils/web_scraper.py` | `cfscrape`-based HTTPS fetcher with randomized User-Agent and 10-second timeout |
| `fincli/utils/quary_builders.py` | Finviz URL construction from filter tuples |
| `fincli/stock_screening/content.py` | Top-level HTML table extractor (BeautifulSoup) |
| `fincli/stock_screening/parsers.py` | Per-row HTML cell parser |
| `fincli/resource/params/fundamental_params.py` | `[query_key, {value_code: display_name}]` definitions for fundamental Finviz filters (P/E, ROE, margins, etc.) |
| `fincli/resource/params/descriptive_params.py` | Descriptive filters (sector, country, market cap, etc.) |
| `fincli/resource/params/technical_params.py` | Technical filters (RSI, SMA, performance, etc.) |
| `fundainsight/app/cli.py` | Click entry point for analysis mode |
| `fundainsight/app/main.py` | `get_opportunities` orchestrator |
| `fundainsight/app/picker.py` | `ThreadPoolExecutor` enrichment + ratio calculation + filter chain |
| `fundainsight/app/fincli.py` | Adapter that re-runs the screener and exposes its DataFrame |
| `fundainsight/calculators/equity_calc.py` | `get_financial_data`, `adjust_assets`, `calculate_price_to_data`, `ratio_between_two_values` |
| `fundainsight/calculators/filters.py` | `Filters` fluent-interface DataFrame filter chain |
| `core/configuration/config_base.py` | `SystemSettings` Pydantic base + `Configurable[S]` generic |
| `core/configuration/configurator.py` | `build_config` builder |
| `core/converters/json.py` | `json_to_tuples` parser for `--set-filters` JSON input |
| `config/config.py` | Concrete `Config(SystemSettings)` with `file_path(name)` CSV-naming helper |
| `logger/logger.py` | Singleton `Logger` (typing console, plain console, JSON file handlers) |
| `singleton.py` | Standalone metaclass utility used by the logger |
| `pyproject.toml` | Project metadata, dev deps, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]` |
| `agents/rules/_shared-workflow.md` | Master workflow rules for AI subagents (lands in C4 of harness rollout) |
| `agents/roles/*.md` | Per-role context files (ARCH / BACKEND / VERIFIER / REVIEWER / QA / FRONTEND / UX_UI) |
| `docs/THESIS.md` | Project vision, current phase, roadmap, scope boundaries |
| `docs/MODULE_REFERENCE.md` | Per-module reference (purpose, public surface, data shapes, error modes) |
| `docs/FEEDBACK-LOG.md` | Append-only log of cross-cutting decisions |
| `docs/superpowers/specs/` | Chronological per-feature design specs |
| `.claude/settings.json` | Hook wiring: `SessionStart` -> `load-rules.js`, `PostToolUse:Edit\|Write` -> `post-edit.js`, `Stop` -> `on-stop.js` |
| `.claude/hooks/load-rules.js` | Auto-injects `_shared-workflow.md`, `preflight.md`, `orchestrator.md` at session start |
| `.claude/hooks/pre-read.js` | Read-time guardrails: blocks reads of secrets/sensitive paths and surfaces stale-cache warnings (C5 work; not yet present) |
| `.claude/hooks/post-edit.js` | Per-edit lint+format+mypy on the saved file; secret/OWASP scan; doc-update reminders |
| `.claude/hooks/on-stop.js` | Repo-wide ruff + mypy + pytest at Stop event; coverage skipped (Phase 3); mypy via `warnings` channel (Phase 4 promotes to gate) |

## Conventions

### Code Style
- **Indentation**: 4 spaces; no tabs.
- **Line length**: 100 (configured in `[tool.ruff]`).
- **Quotes**: double (`"foo"`); ruff format enforces this.
- **Imports**: `ruff` rule `I` (import order) auto-fixes.
- **Type hints**: encouraged; `[tool.mypy] strict = true` from day one. The codebase has very few hints today, so `strict` produces hundreds of errors — this is expected and **advisory only in Phase 1** (see "Phase status" below). Adding hints is the natural way to drive that count down.
- **Docstrings**: **Google style** (`Args:` / `Returns:` / `Raises:` blocks). Phase 1 does not enable ruff `D` rules; Phase 4 may enable them once the type-hint pass is far enough along.

### Logging
- **Always** import the Singleton: `from logger import logger`. Never construct your own `logging.Logger`. Never use `print` in non-CLI paths.
- The logger has three handlers (typing-effect console, plain console, JSON file). Use `.info`, `.warning`, `.error`, `.debug`. Pass the message as a single string; no positional `%` formatting (`f`-strings are fine).
- The logger writes to `logs/activity.log` (DEBUG+) and `logs/error.log` (ERROR+) on top of stdout.

### Configuration
- **Always** use `Config` (`config/config.py`) extended from `SystemSettings` (`core/configuration/config_base.py`).
- New settings get added as Pydantic fields on `Config` with sensible defaults. Pydantic does the validation; do not hand-roll validators outside `model_validator`.
- The `file_path(name)` helper produces `workspace_output/{name}_{YYYY-MM-DD_HH-MM}.csv`. Use it for any new CSV output to keep file naming uniform.

### CLI Surface
- Every operating mode is a `@click.group(invoke_without_command=True)` so that running `python -m <mode>` with no subcommand does the default thing.
- New options follow the existing pattern: `--<name>` (kebab) with optional alias, `is_flag=True` for booleans, `default=""` for string-valued ones.

### Concurrency
- Synchronous everywhere except the Yahoo enrichment loop in `fundainsight/app/picker.py`, which uses `concurrent.futures.ThreadPoolExecutor`.
- If you add a new fan-out step, prefer `ThreadPoolExecutor` over hand-rolled threads — same idiom, same logger thread-safety, easy to limit max workers later.

### File / CSV Output
- All persistent results land in `workspace_output/` (gitignored). Never write to repo root.
- File names always include the `YYYY-MM-DD_HH-MM` timestamp via `Config.file_path`.
- The `Ticker` column in the screener CSV is wrapped as an Excel `=HYPERLINK(...)` formula. Preserve that when adding new columns adjacent to it.

### Testing
- Test layout (Phase 2 work): `tests/unit/`, `tests/domain/`, `tests/e2e/`.
- See `TESTING.md` for fixtures, mocking strategy, and which dependencies are mockable vs. real.

## MCP Tool Usage

These MCP servers are wired in this repo. One-line "when to use" guidance:

| Tool | When to reach for it |
|---|---|
| `sequential-thinking` | Multi-step reasoning where you need to break a problem into ordered steps and write them down before acting (long debug chains, refactor planning). |
| `memory` | Persistent cross-session knowledge graph for project-level facts (data shapes, decisions). Don't use for transient session state. |
| `perplexity-ask` | Web research / "how do other projects solve X". Useful for library comparisons, idiom lookups. |
| `context7` | Library documentation lookups (Click, pandas, Pydantic, yahooquery, cfscrape) — preferred over web search for library docs. |
| `zen-mcp__thinkdeep` | Deep architectural reasoning where you want a second model to chew on a question. |
| `zen-mcp__codereview` | Pre-PR systematic review pass on changed files. |
| `zen-mcp__debug` | Root-cause analysis when a bug resists fix-and-retry. |

A full reference of all available skills, slash commands, and MCP tools (including how to call each) lives in `TOOLS_REFERENCE.md`.

## Common Gotchas

- The `pyproject.toml` originally listed `yfinance`, but the actual import is `yahooquery`. The harness work in C1 corrected this; do not let it drift back. Use `yahooquery` everywhere.
- `requirements.txt` pins `urllib3<2`. Do not bump it without testing `cfscrape` end-to-end against Finviz; cfscrape's transitive dependency expects the v1 API.
- `cfscrape` and `yahooquery` ship no inline type info and no community stubs on PyPI. They are listed under `[[tool.mypy.overrides]]` with `ignore_missing_imports = true` in `pyproject.toml` to silence `import-untyped` errors. Do not remove that override.
- `bs4` is typed via the `types-beautifulsoup4` dev dependency; mypy needs no override for it.
- `singleton.py` lives at the repo root, not under `core/`. The logger imports it as a top-level module.
- `get_financial_data(ticker)` in `fundainsight/calculators/equity_calc.py` returns `None` on any failure path. Downstream code (`picker.py`) assumes `None` rows are filtered before ratio math. If you change this contract, update both sides in lockstep.
- `picker.py` has hardcoded country/sector exclusions (`Brazil, Chile, India, Bermuda, China`, sector `Energy`). They are tracked as configurability tech debt below — do not add more hardcoded filters without surfacing them as configuration.
- The `tests/` folder has `__pycache__` content from previously-deleted test bodies. Phase 2 introduces real tests; do not remove the folder structure.
- `wisdom_fruit/` is experimental and not on the runtime path. Do not import from it.
- `shared/`, `example/`, and `src/` are empty scaffolds; cleaning them up is queued tech debt, not a current task.

## Known Issues / Tech Debt

- **`equity_calc.adjust_assets()` `not int` truthy-check bug.** The function uses `... if not int else ...` in several places. `int` is the type object, which is always truthy, so `not int` is always `False`, meaning the second branch always runs. The intent was almost certainly a `len()` / size check that got mis-typed. Phase 2 will write a regression test that pins the *current* behavior, then fix the bug, then update the test.
- **Hardcoded filters in `picker.py`** (`filter_countries(...)`, `filter_sector("Energy")`, ratio threshold `1`). These should move into `Config` so they are user-overridable per run.
- **No tests today.** Folder structure exists; bodies arrive in Phase 2.
- **`wisdom_fruit/`** is incomplete and abandoned — slated for removal once it is confirmed nothing depends on it.
- **`shared/`, `example/`, `src/finpack/`** are empty scaffolds left behind by an earlier reorganization. Removing them is queued.
- **`mypy strict = true` produces a large day-one error count** because the codebase has almost no type hints. This is intentional — see Phase 4 below. Do not weaken `strict` to silence the count; instead add hints to the file you are editing.
- **Hard-coded history path in `core/configuration/configurator.py`** — `build_config` derives the `filter_history.json` location from `os.path.realpath('fundainsight')` regardless of which CLI invoked it. `fincli --history` therefore reads/writes to `fundainsight/local_history/` rather than `fincli/local_history/`. Phase 2 fix candidate.

## Phase Status

This codebase is in the middle of an "agent harness" rollout that mirrors the Midas project's harness onto algo_beta. Tracked in `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.

| Phase | What | Status |
|---|---|---|
| Phase 1 | Bootstrap Python tooling (Ruff, mypy strict, pytest config), rewrite top-level docs (`ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, plus new `TOOLS_REFERENCE.md` and `AGENTS.md`), scaffold `agents/` and `docs/` folders, install Claude Code hooks. **Phase 1 is in progress as of 2026-05-02.** | In progress |
| Phase 2 | Introduce real `pytest` test suite for `fundainsight/calculators/`, `core/configuration/`, and the screener pipeline. Add HTML / yahooquery fixtures. Add type hints incrementally to the modules being tested — driving the mypy advisory count down. Fix the `equity_calc.adjust_assets` `not int` bug as part of writing its tests. | Deferred |
| Phase 3 | Enable the coverage gate in `.claude/hooks/on-stop.js` at **90%** (matching Midas). Update `TESTING.md`, `agents/roles/verifier.md`, and `agents/rules/_shared-workflow.md` to reflect the enforced threshold. | Deferred |
| Phase 4 | Promote mypy from `warnings` channel to `issues` channel in `on-stop.js` (and from advisory to blocking in `post-edit.js`) once `mypy fundainsight fincli core config` reports zero errors. Optionally enable ruff `D` rules (Google docstring enforcement) at the same time. | Deferred |

The deferral structure is intentional: a coverage gate against zero tests is meaningless, and a strict-mypy gate against an unannotated codebase trains people to ignore failing hooks. Phases are unlocked in order. Each has a concrete trigger condition documented in §8 of the spec.
