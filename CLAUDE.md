# CLAUDE.md - Fin CLI

This file provides guidance for AI assistants (Claude, etc.) working on this codebase.

READING `AGENTS.md` IS MANDATORY.

## Project Overview

**Fin CLI** is a Python package exposing a Finviz.com stock screener through two co-equal entry points: a CLI (`fincli/`) and an HTTP API (`fincli_api/`). Both consume the same orchestrator (`fincli.app.main.screen_to_dataframe`) and the same filter inventory (`fincli.resource.params.validators.list_valid_filters_with_labels`), so the contract cannot drift across surfaces.

- **CLI (`fincli/`)** has two usage shapes that share the same orchestrator — the original interactive picker (Fundamental / Descriptive / Technical filter selection) and a pipeline mode (structured `--filter`/`--filters-json`/`--filters-file` input, deterministic `--output`/`--output -` destination, stream discipline via `--quiet`/`--json-summary`, and differentiated exit codes 0/1/2/3/4). Pipeline mode shipped on 2026-05-16 — see `docs/features/archive/pipeline-mode-spec.md`.
- **HTTP API (`fincli_api/`)** is a FastAPI surface exposing `GET /filters`, `POST /screens`, and `GET /healthz`, with an OpenAPI 3.1.0 snapshot committed at `docs/api/openapi.{yaml,json}`. Shipped 2026-05-24 — see `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`.

Both entry points build the corresponding Finviz URL, fetch every paginated result page through `cfscrape` (Cloudflare-bypassing HTTPS client), parse the HTML stock table with BeautifulSoup, and return the result as a DataFrame (CLI writes it to a timestamped CSV or stdout; API serializes it to JSON).

- **Language / runtime**: Python 3.12+
- **Packaging**: `pyproject.toml` (PEP 621); editable install via `pip install -e ".[dev]"`. Distribution name is `fincli`.
- **Distribution**: source-only; no PyPI release at this time
- **Stack**: Click (CLI), FastAPI + uvicorn + pydantic-settings (HTTP API), pandas (data), cfscrape (Cloudflare bypass), BeautifulSoup4 (HTML parsing), Pydantic (config validation), colorama (ANSI colors), platformdirs (user-data-directory resolution)

## Build & Run

```bash
# Install the project + dev tooling in editable mode
pip install -e ".[dev]"

# Run the CLI screener
python -m fincli                        # interactive
python -m fincli --history              # reuse last filter selection
python -m fincli --debug                # verbose logging
python -m fincli --list-filters --json  # dump filter inventory

# Or use the convenience launchers
./run.sh                        # Linux / macOS
run.bat                         # Windows

# Run the HTTP API
uvicorn fincli_api.main:app --reload    # dev: auto-reload on code changes
fincli-api                              # via console-script entry (binds 0.0.0.0:8000 by default)
# Then curl http://localhost:8000/healthz, GET /filters, POST /screens
# Or visit http://localhost:8000/docs for Swagger UI

# Regenerate the OpenAPI snapshot (committed at docs/api/openapi.{yaml,json})
python scripts/dump_openapi.py          # write fresh snapshot
python scripts/dump_openapi.py --check  # drift-detection (CI-suitable; non-zero exit if drift)

# Tests
pytest tests/                           # full suite (skips live-Finviz gate by default)
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/
pytest -m live tests/e2e/api/           # opt-in live-Finviz smoke (~3s, network-dependent)

# Lint + format (Ruff)
ruff check .
ruff check --fix .
ruff format .
ruff format --check .

# Type-check (mypy strict)
mypy fincli fincli_api core config logger
mypy --no-incremental         # bypass cache when diagnosing weirdness

# Vulnerability audit (when pip-audit is on PATH; gracefully skipped otherwise)
pip-audit -r requirements.txt
```

`workspace_output/` accumulates CSVs from each run. It is `.gitignore`d.

## Architecture

Two co-equal entry points (CLI + HTTP API) sharing one screener orchestrator + configuration + logger plumbing. Layers:

```
Click CLI                  ->  Orchestration (fincli/app/main.py)  ->  Filter UI / Web scraper / BeautifulSoup parser  ->  External service (Finviz HTML)
FastAPI (fincli_api/main)  ->  Adapter (fincli_api/adapters/fincli.py)  ->  same Orchestration
```

There is no DI container, no database. Wiring is by direct import; the HTTP API's adapter is the ONLY file in `fincli_api/` allowed to import from `fincli/` (architectural boundary per spec §3.2). The Singleton logger is the only globally-visible runtime object. The runtime is fully synchronous so the scraper cooperates with Finviz's anti-bot pacing; FastAPI runs sync handlers in its default thread pool.

Full diagram + per-section detail in `ARCHITECTURE.md`.

## Important Files

| File | Purpose |
|---|---|
| `fincli/app/cli.py` | Click entry point for the screener (all 9 options + mutual-exclusion + input normalization + banner gate) |
| `fincli/app/main.py` | Screener pipeline orchestrator (`run_stock_screener`, `fetch_urls`, `aggregate_rows`, `build_data_frame`, `_emit_run_tail`, `_build_summary`). Wraps the pipeline in a try/except classifier and calls `sys.exit(<code>)` via `fincli.app.exit_codes.classify`. |
| `fincli/app/exit_codes.py` | Pillar-4 exit-code constants (`SUCCESS=0`/`INTERNAL=1`/`USAGE=2`/`UPSTREAM=3`/`DATA=4`) and the `classify(exc)` function. |
| `fincli/utils/market_cap.py` | `convert_market_cap_to_numeric(value)` — coerces Finviz `Market Cap` cells to a nullable `Float64` value or `pandas.NA`. Carved out of `fincli/app/main.py` in commit `50f46ca` for direct testability. |
| `fincli/resource/params/validators.py` | `validate_filter_pairs(pairs)` — strict-validates structured filter input against the Finviz inventory; raises `click.UsageError` (exit 2) on unknown key/value. |
| `fincli/cli/cli_stock_screener.py` | Interactive filter-selection UI. `prompt_section` displays each filter group (Fundamental / Descriptive / Technical) one at a time with per-section local 1-based numbering; blank input skips a section, out-of-range or non-integer input reprompts. |
| `fincli/utils/web_scraper.py` | `cfscrape`-based HTTPS fetcher with randomized User-Agent and 10-second timeout |
| `fincli/utils/quary_builders.py` | Finviz URL construction from filter tuples |
| `fincli/stock_screening/content/stock_table.py` | Top-level HTML table extractor (BeautifulSoup) |
| `fincli/stock_screening/parsers/stock_table.py` | Per-row HTML cell parser |
| `fincli/stock_screening/locators/stock_table_locators.py` | CSS / element locators for the Finviz screener table |
| `fincli/resource/params/fundamental_params.py` | `[query_key, {value_code: display_name}]` definitions for fundamental Finviz filters (P/E, ROE, margins, etc.) |
| `fincli/resource/params/descriptive_params.py` | Descriptive filters (sector, country, market cap, etc.) |
| `fincli/resource/params/technical_params.py` | Technical filters (RSI, SMA, performance, etc.) |
| `fincli_api/main.py` | FastAPI app composition + `main()` uvicorn entry bound to the `fincli-api` script |
| `fincli_api/config.py` | `ApiConfig` via pydantic-settings (host/port/log_level; `FINCLI_API_` env prefix) |
| `fincli_api/routes/{filters,screens,meta}.py` | 3 routers: `GET /filters`, `POST /screens` (with `validate_filter_pairs` gate per silent-drop hazard), `GET /healthz` |
| `fincli_api/adapters/fincli.py` | Boundary layer — the ONLY file in `fincli_api/` allowed to import from `fincli/`. Two functions: `get_filter_inventory()`, `run_screen()`. |
| `fincli_api/models/{filters,screens,errors}.py` | Pydantic request/response shapes + `ErrorResponse` envelope with `Literal[validation/upstream/parsing/internal]` discriminator |
| `fincli_api/exception_handlers.py` | `register_exception_handlers(app)` — single classifier-driven envelope via `fincli.app.exit_codes.classify` |
| `scripts/dump_openapi.py` | Regenerate `docs/api/openapi.{yaml,json}`; supports `--check` for drift detection |
| `docs/api/openapi.{yaml,json}` | Committed OpenAPI 3.1.0 snapshot — polyglot-consumer contract artifact |
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
| `docs/features/` | Feature-restoration / feature-addition specs (`<topic>-spec.md`); shipped specs move to `archive/` |
| `docs/pendingwork/` | Session handoff docs (`YYYY-MM-DD-session-handoff.md`); historical handoffs move to `archive/` |
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
- **HTTP API**: FastAPI endpoints are sync functions (`def`, not `async def`) — fincli's pipeline is fully sync, and FastAPI runs sync handlers in its thread pool at single-user load. No subprocess; the adapter imports fincli directly.

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
- `pyproject.toml` declares `[tool.setuptools.packages.find]` with `include = ["fincli*", "fincli_api*", "core*", "config*", "logger*"]` plus `[tool.setuptools] py-modules = ["singleton"]`. Modern setuptools (>= 67) refuses to auto-discover when a flat-layout repo has more than one top-level package; this directive is what makes `pip install -e .` succeed. Don't remove it without restructuring the repo to a `src/` layout.
- **`pytest.ini` is the canonical pytest config**, not `pyproject.toml`'s `[tool.pytest.ini_options]`. Pytest precedence picks `pytest.ini` first when both exist; the pyproject section was stripped to an explanatory comment in T5c. Don't reintroduce settings into pyproject — port to `pytest.ini`.
- **Mock target for fincli HTTP in API tests must be `fincli.app.main.fetch_page_sync`**, NOT `fincli.utils.web_scraper.fetch_page_sync`. The former is the local-name binding via `from ... import fetch_page_sync` in `main.py`; patching the original location doesn't affect what `main.py` already imported. T5b's conftest documents the rule.
- **Malformed HTML may currently coerce to 200 empty** instead of spec §5.1's 502 parsing error (MAJOR #4 deferred). Future parser fix in `fincli/stock_screening/` will need to coordinate with the xfail-pair pattern at `tests/integration/api/test_screens_integration.py`.

## Known Issues / Tech Debt

- **Phase-2 test seed shipped (2026-05-16) — 200+ tests across `tests/unit/` and `tests/integration/`.** Coverage gate (Phase 3) still deferred until the suite stabilizes and the gate's value vs. friction has been measured against the real cadence.
- **`mypy strict = true` produces a non-zero day-one error count** because the codebase still has many untyped modules. This is intentional — see Phase 4 below. Do not weaken `strict` to silence the count; instead add hints to the file you are editing. The pipeline-mode rollout drove typing-coverage up across `fincli/app/`, `fincli/utils/market_cap.py`, `fincli/resource/params/validators.py`, `core/converters/json.py`, and `logger/`; legacy modules (BS4 parsers, web scraper, query builder) still lag.
- **`Logger.error(title, message="")` parameter order is flipped** relative to `debug` / `info` / `warn` (which are `(message, title="")`). Pre-existing footgun documented in `docs/MODULE_REFERENCE.md`. Use the documented order; do not "fix" it because every existing caller relies on the flipped shape.

## Phase Status

This codebase is in the middle of an "agent harness" rollout that mirrors the Midas project's harness onto fin_cli. Tracked in `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`. Phase 2 scope was retargeted by the single-mode reduction (`docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`).

| Phase | What | Status |
|---|---|---|
| Phase 1 | Bootstrap Python tooling (Ruff, mypy strict, pytest config), rewrite top-level docs (`ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, plus new `TOOLS_REFERENCE.md` and `AGENTS.md`), scaffold `agents/` and `docs/` folders, install Claude Code hooks. **Phase 1 is in progress as of 2026-05-02.** | In progress |
| Phase 2 | Introduce real `pytest` test suite for `fincli/stock_screening/` and the screener pipeline. Add HTML fixtures. Add type hints incrementally to the modules being tested — driving the mypy advisory count down. | Deferred |
| Phase 3 | Enable the coverage gate in `.claude/hooks/on-stop.js` at **90%** (matching Midas). Update `TESTING.md`, `agents/roles/verifier.md`, and `agents/rules/_shared-workflow.md` to reflect the enforced threshold. | Deferred |
| Phase 4 | Promote mypy from `warnings` channel to `issues` channel in `on-stop.js` (and from advisory to blocking in `post-edit.js`) once `mypy fincli core config logger` reports zero errors. Optionally enable ruff `D` rules (Google docstring enforcement) at the same time. | Deferred |
| Phase 5 | HTTP API mode — Add `fincli_api/` sibling package exposing a FastAPI surface (`GET /filters`, `POST /screens`, `GET /healthz`). OpenAPI 3.1.0 auto-generated from Pydantic models and committed to `docs/api/openapi.{yaml,json}` via `scripts/dump_openapi.py`. 3-tier test pyramid (unit / integration with mocked Finviz / e2e with live Finviz behind `-m live`). Shipped 2026-05-24 — see `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`. | **Shipped** |

The deferral structure is intentional: a coverage gate against zero tests is meaningless, and a strict-mypy gate against an unannotated codebase trains people to ignore failing hooks. Phases are unlocked in order. Each has a concrete trigger condition documented in §8 of the harness rollout spec.
