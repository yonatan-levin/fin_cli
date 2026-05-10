# CLAUDE.md - Fin CLI

This file provides guidance for AI assistants (Claude, etc.) working on this codebase.

READING `AGENTS.md` IS MANDATORY.

## Project Overview

**Fin CLI** is a Python command-line application for stock screening. It is a single-mode tool: an interactive Finviz.com stock screener. The user picks filter values from the standard Finviz vocabulary (P/E, sector, country, RSI, etc.); the tool builds the corresponding Finviz URL, fetches every paginated result page through `cfscrape` (Cloudflare-bypassing HTTPS client), parses the HTML stock table with BeautifulSoup, and writes the result to a timestamped CSV.

- **Language / runtime**: Python 3.12+
- **Packaging**: `pyproject.toml` (PEP 621); editable install via `pip install -e ".[dev]"`. Distribution name is `fincli`.
- **Distribution**: source-only; no PyPI release at this time
- **Stack**: Click (CLI), pandas (data), cfscrape (Cloudflare bypass), BeautifulSoup4 (HTML parsing), Pydantic (config validation), colorama (ANSI colors)

## Build & Run

```bash
# Install the project + dev tooling in editable mode
pip install -e ".[dev]"

# Run the screener
python -m fincli                # interactive
python -m fincli --history      # reuse last filter selection
python -m fincli --debug        # verbose logging

# Or use the convenience launchers
./run.sh                        # Linux / macOS
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
mypy fincli core config logger
mypy --no-incremental         # bypass cache when diagnosing weirdness

# Vulnerability audit (when pip-audit is on PATH; gracefully skipped otherwise)
pip-audit -r requirements.txt
```

`workspace_output/` accumulates CSVs from each run. It is `.gitignore`d.

## Architecture

Single-mode CLI with shared configuration and logger plumbing. Layers:

```
Click CLI  ->  Orchestration (fincli/app/main.py)
            ->  Filter UI / Web scraper / BeautifulSoup parser
            ->  External service (Finviz HTML)
```

There is no DI container, no server, no database. Wiring is by direct import. The Singleton logger is the only globally-visible runtime object. The runtime is fully synchronous so the scraper cooperates with Finviz's anti-bot pacing.

Full diagram + per-section detail in `ARCHITECTURE.md`.

## Important Files

| File | Purpose |
|---|---|
| `fincli/app/cli.py` | Click entry point for the screener |
| `fincli/app/main.py` | Screener pipeline orchestrator (`run_stock_screener`, `fetch_urls`, `aggregate_rows`, `build_data_frame`, `convert_market_cap_to_numeric`) |
| `fincli/cli/cli_stock_screener.py` | Interactive filter-selection UI. `prompt_section` displays each filter group (Fundamental / Descriptive / Technical) one at a time with per-section local 1-based numbering; blank input skips a section, out-of-range or non-integer input reprompts. |
| `fincli/utils/web_scraper.py` | `cfscrape`-based HTTPS fetcher with randomized User-Agent and 10-second timeout |
| `fincli/utils/quary_builders.py` | Finviz URL construction from filter tuples |
| `fincli/stock_screening/content/stock_table.py` | Top-level HTML table extractor (BeautifulSoup) |
| `fincli/stock_screening/parsers/stock_table.py` | Per-row HTML cell parser |
| `fincli/stock_screening/locators/stock_table_locators.py` | CSS / element locators for the Finviz screener table |
| `fincli/resource/params/fundamental_params.py` | `[query_key, {value_code: display_name}]` definitions for fundamental Finviz filters (P/E, ROE, margins, etc.) |
| `fincli/resource/params/descriptive_params.py` | Descriptive filters (sector, country, market cap, etc.) |
| `fincli/resource/params/technical_params.py` | Technical filters (RSI, SMA, performance, etc.) |
| `core/configuration/config_base.py` | `SystemSettings` Pydantic base + `Configurable[S]` generic |
| `core/configuration/configurator.py` | `build_config` builder |
| `core/converters/json.py` | `json_to_tuples` parser for JSON filter input |
| `config/config.py` | Concrete `Config(SystemSettings)` with `file_path(name)` CSV-naming helper |
| `logger/logger.py` | Singleton `Logger` (typing console, plain console, JSON file handlers) |
| `singleton.py` | Standalone metaclass utility used by the logger |
| `pyproject.toml` | Project metadata, dev deps, `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`, `[tool.setuptools]` (explicit flat-layout package discovery) |
| `agents/rules/_shared-workflow.md` | Master workflow rules for AI subagents |
| `agents/roles/*.md` | Per-role context files (8 roles) |
| `docs/THESIS.md` | Project vision, current phase, roadmap, scope boundaries |
| `docs/MODULE_REFERENCE.md` | Per-module reference (purpose, public surface, data shapes, error modes) |
| `docs/FEEDBACK-LOG.md` | Append-only log of cross-cutting decisions |
| `docs/superpowers/specs/` | Chronological per-feature design specs |
| `docs/refactoring/` | Cross-cutting refactor specs (`<topic>-spec.md`); shipped specs move to `archive/` |
| `.claude/settings.json` | Hook wiring: `SessionStart` -> `load-rules.js`, `PostToolUse:Edit\|Write` -> `post-edit.js`, `Stop` -> `on-stop.js` |
| `.claude/hooks/load-rules.js` | Auto-injects `_shared-workflow.md`, `preflight.md`, `orchestrator.md` at session start |
| `.claude/hooks/post-edit.js` | Per-edit lint+format+mypy on the saved file; secret/OWASP scan; doc-update reminders |
| `.claude/hooks/on-stop.js` | Repo-wide ruff + mypy + pytest at Stop event; coverage skipped (Phase 3); mypy via `warnings` channel (Phase 4 promotes to gate) |

## Conventions

### Code Style
- **Indentation**: 4 spaces; no tabs.
- **Line length**: 100 (configured in `[tool.ruff]`).
- **Quotes**: double (`"foo"`); ruff format enforces this.
- **Imports**: `ruff` rule `I` (import order) auto-fixes.
- **Type hints**: encouraged; `[tool.mypy] strict = true` from day one. The codebase has very few hints today, so `strict` produces dozens of errors — this is expected and **advisory only in Phase 1** (see "Phase status" below). Adding hints is the natural way to drive that count down.
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
- The screener entry point is a `@click.group(invoke_without_command=True)` so that running `python -m fincli` with no subcommand does the default thing.
- New options follow the existing pattern: `--<name>` (kebab) with optional alias, `is_flag=True` for booleans, `default=""` for string-valued ones.

### Concurrency
- The runtime is fully synchronous. Pages from Finviz are fetched one at a time so the scraper does not flood Cloudflare's pacing.
- If a future change needs fan-out, prefer `concurrent.futures.ThreadPoolExecutor` over hand-rolled threads — the Singleton logger is already thread-safe and the executor is easy to bound at the call site.

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
| `context7` | Library documentation lookups (Click, pandas, Pydantic, cfscrape, BeautifulSoup4) — preferred over web search for library docs. |
| `zen-mcp__thinkdeep` | Deep architectural reasoning where you want a second model to chew on a question. |
| `zen-mcp__codereview` | Pre-PR systematic review pass on changed files. |
| `zen-mcp__debug` | Root-cause analysis when a bug resists fix-and-retry. |

A full reference of all available skills, slash commands, and MCP tools (including how to call each) lives in `TOOLS_REFERENCE.md`.

## Common Gotchas

- `requirements.txt` pins `urllib3<2`. Do not bump it without testing `cfscrape` end-to-end against Finviz; cfscrape's transitive dependency expects the v1 API.
- `cfscrape` ships no inline type info and no community stubs on PyPI. It is listed under `[[tool.mypy.overrides]]` with `ignore_missing_imports = true` in `pyproject.toml` to silence `import-untyped` errors. Do not remove that override.
- `bs4` is typed via the `types-beautifulsoup4` dev dependency; mypy needs no override for it.
- `singleton.py` lives at the repo root, not under `core/`. The logger imports it as a top-level module.
- The `tests/` folder has `__pycache__` content from previously-deleted test bodies. Phase 2 introduces real tests; do not remove the folder structure.
- The package is installed as `fincli` (PEP 621 distribution name in `pyproject.toml`). It used to be `finscrape`; if pip is reusing a stale egg-info, `pip uninstall finscrape` then `pip install -e ".[dev]"` from a clean venv.
- `pyproject.toml` declares `[tool.setuptools.packages.find]` with `include = ["fincli*", "core*", "config*", "logger*"]` plus `[tool.setuptools] py-modules = ["singleton"]`. Modern setuptools (>= 67) refuses to auto-discover when a flat-layout repo has more than one top-level package; this directive is what makes `pip install -e .` succeed. Don't remove it without restructuring the repo to a `src/` layout.

## Known Issues / Tech Debt

- **No tests today.** Folder structure exists; bodies arrive in Phase 2.
- **`mypy strict = true` produces a non-zero day-one error count** because the codebase has almost no type hints. This is intentional — see Phase 4 below. Do not weaken `strict` to silence the count; instead add hints to the file you are editing.

## Phase Status

This codebase is in the middle of an "agent harness" rollout that mirrors the Midas project's harness onto fin_cli. Tracked in `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`. Phase 2 scope was retargeted by the single-mode reduction (`docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`).

| Phase | What | Status |
|---|---|---|
| Phase 1 | Bootstrap Python tooling (Ruff, mypy strict, pytest config), rewrite top-level docs (`ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, plus new `TOOLS_REFERENCE.md` and `AGENTS.md`), scaffold `agents/` and `docs/` folders, install Claude Code hooks. **Phase 1 is in progress as of 2026-05-02.** | In progress |
| Phase 2 | Introduce real `pytest` test suite for `fincli/stock_screening/` and the screener pipeline. Add HTML fixtures. Add type hints incrementally to the modules being tested — driving the mypy advisory count down. | Deferred |
| Phase 3 | Enable the coverage gate in `.claude/hooks/on-stop.js` at **90%** (matching Midas). Update `TESTING.md`, `agents/roles/verifier.md`, and `agents/rules/_shared-workflow.md` to reflect the enforced threshold. | Deferred |
| Phase 4 | Promote mypy from `warnings` channel to `issues` channel in `on-stop.js` (and from advisory to blocking in `post-edit.js`) once `mypy fincli core config logger` reports zero errors. Optionally enable ruff `D` rules (Google docstring enforcement) at the same time. | Deferred |

The deferral structure is intentional: a coverage gate against zero tests is meaningless, and a strict-mypy gate against an unannotated codebase trains people to ignore failing hooks. Phases are unlocked in order. Each has a concrete trigger condition documented in §8 of the harness rollout spec.
