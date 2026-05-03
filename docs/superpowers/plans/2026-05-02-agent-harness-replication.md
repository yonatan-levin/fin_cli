# Algo Beta Agent Harness Replication — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replicate the full Midas agent harness (AGENTS.md loading contract, `.claude/` hooks, `agents/` roles + rules, `docs/` tree) in algo_beta, retargeted from Go/REST to Python/CLI semantics, with ruff + mypy (strict, advisory) + pytest tooling. Zero source-code changes.

**Architecture:** Single PR composed of 6 logical commits: (1) foundation tooling, (2) top-level docs, (3) docs/ tree, (4) agents/ folder, (5) hooks, (6) settings + final wiring. Each commit leaves the repo in a coherent state. Hooks reference rules; rules reference docs; AGENTS.md indexes everything — so order matters within and across commits.

**Tech Stack:** Python 3.12+, Click CLI, pandas, yahooquery, cfscrape, BeautifulSoup4, Pydantic, colorama. Tooling: ruff (lint+format), mypy (strict, advisory in Phase 1), pytest, pip-audit. Hook scripts: Node.js (the existing midas hook infrastructure).

**Spec reference:** `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` (rev 0.2, approved 2026-05-02).

**Source-of-truth Midas project:** `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\`

**Branch strategy:** Implementation should happen on a feature branch (`feat/agent-harness`) or a worktree, NOT directly on `master`. The implementer's first action is to create that branch. Existing untracked top-level docs (ARCHITECTURE.md, CLAUDE.md, CONTRACTS.md, TESTING.md) should be committed as a baseline first so the rewrite diff is reviewable.

---

## File Structure

After this plan executes, the following files will exist or be modified:

### NEW files
- `AGENTS.md`, `TOOLS_REFERENCE.md`
- `.claude/settings.json`
- `.claude/hooks/{load-rules,pre-read,post-edit,on-stop,utils}.js` + `.gitignore`
- `agents/roles/*.md` (8 files), `agents/rules/*.md` (5 files)
- `docs/THESIS.md`, `docs/FEEDBACK-LOG.md`, `docs/MODULE_REFERENCE.md`
- `docs/{bugs,refactoring,reviewer}/README.md` + each `archive/` subfolder
- `docs/superpowers/plans/` (this file already lives here)

### REWRITTEN files
- `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`

### MODIFIED files
- `pyproject.toml` (add tool sections + dev deps + fix yfinance→yahooquery)
- `.gitignore` (add hook session-state ignores)
- `.claude/settings.local.json` (merge in Python permissions)

### DELETED
- `.claude/agnets/` (empty typo directory)

### UNTOUCHED
- All source code (`fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `scripts/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`)
- `requirements.txt`, existing test folders, `singleton.py`

---

## Commit Plan

Six logical commits, in this order:

| # | Commit subject | Tasks |
|---|---|---|
| C0 | `chore: snapshot pre-rewrite docs as baseline` | T0 |
| C1 | `chore: bootstrap Python tooling + cleanup` | T1–T4 |
| C2 | `docs: rewrite top-level docs in Midas style` | T5–T11 |
| C3 | `docs: scaffold docs/ tree (THESIS, FEEDBACK-LOG, MODULE_REFERENCE, subfolders)` | T12–T15 |
| C4 | `chore: add agents/ folder (rules + roles)` | T16–T17 |
| C5 | `feat: wire .claude/ hook harness` | T18–T22 |
| C6 | `chore: wire .claude/settings.json + final validation` | T23–T25 |

---

## Task 0: Branch + Snapshot Baseline

**Files:**
- All of: `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md` (modified), `TESTING.md`, `.gitignore` (modified) — currently untracked or unstaged

- [ ] **Step 1: Create feature branch from master**

```bash
cd "C:/Users/Yonatan Levin/Documents/Programming/Projects/FinTech/Strade/algo_beta"
git checkout -b feat/agent-harness
```

Expected: switched to new branch `feat/agent-harness`.

- [ ] **Step 2: Commit existing untracked top-level docs as baseline**

```bash
git add ARCHITECTURE.md CLAUDE.md CONTRACTS.md TESTING.md
git status
```

Expected: 4 staged files. (`README.md` already exists in history; current modifications stay unstaged for now.)

- [ ] **Step 3: Commit baseline**

```bash
git commit -m "chore: snapshot pre-rewrite top-level docs as baseline"
```

Expected: clean commit with the four currently-untracked Markdown files.

---

## Task 1: pyproject.toml — fix dependencies + add tool sections

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Read current pyproject.toml to confirm shape**

```bash
cat pyproject.toml
```

Expected: see `[project] name = "finscrape"` block with stale `yfinance` dep and doubled `requests`/`urllib3<2`.

- [ ] **Step 2: Replace pyproject.toml with extended config**

Write the file to:

```toml
[project]
name = "finscrape"
version = "0.1.0"
requires-python = ">=3.12"

dependencies = [
    "requests",
    "urllib3<2",
    "pandas",
    "yahooquery",
    "cfscrape",
    "click",
    "pydantic",
    "colorama",
    "beautifulsoup4",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.6",
    "mypy>=1.10",
    "pytest>=8",
    "pytest-cov>=5",
    "types-beautifulsoup4",
    "pip-audit",
]

[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = [
    "workspace_output",
    "workspace_materials",
    "dist",
    "htmlcov",
    "wisdom_fruit",
    "shared",
    "example",
    "src",
    "benchmarks",
    "__pycache__",
    ".venv",
]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "N", "SIM"]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.12"
files = ["fundainsight", "fincli", "core", "config", "logger"]
strict = true
warn_unused_ignores = true
show_error_codes = true

[[tool.mypy.overrides]]
module = ["cfscrape", "cfscrape.*", "yahooquery", "yahooquery.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_classes = "Test*"
python_functions = "test_*"
addopts = "-ra"
```

- [ ] **Step 3: Verify the file parses**

```bash
python -c "import tomllib; tomllib.loads(open('pyproject.toml','rb').read().decode())"
```

Expected: no output (parse succeeded). If `tomllib` isn't available (<3.11), use `pip install tomli` and `import tomli`.

- [ ] **Step 4: Verify yfinance is gone**

```bash
grep -c yfinance pyproject.toml
```

Expected: `0`.

---

## Task 2: Install dev tooling

**Files:**
- None modified; just installs

- [ ] **Step 1: Install dev dependencies**

```bash
pip install -e ".[dev]"
```

Expected: ruff, mypy, pytest, pytest-cov, types-beautifulsoup4, pip-audit installed.

- [ ] **Step 2: Smoke-check each tool reports a version**

```bash
ruff --version && mypy --version && pytest --version && pip-audit --version
```

Expected: each prints a version string. If any fails, fix install before continuing.

- [ ] **Step 3: First ruff run — establish baseline**

```bash
ruff check . | head -50
```

Expected: some findings (acceptable for Phase 1 baseline). Note the count to compare after future tasks.

- [ ] **Step 4: First mypy run — confirm strict expected error volume**

```bash
mypy fundainsight fincli core config logger 2>&1 | tail -5
```

Expected: many errors (hundreds). The last line is something like `Found N errors in M files`. Record N — Phase 4's exit criterion is N=0.

---

## Task 3: .gitignore hardening

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Read current .gitignore tail**

```bash
tail -20 .gitignore
```

Expected: see existing trailing content, identify a clean append point.

- [ ] **Step 2: Append hook session-state ignores**

Append to `.gitignore`:

```
# Claude Code hook session state
.claude/hooks/.session-edits.json
.claude/hooks/.rules-loaded
.claude/projects/
```

- [ ] **Step 3: Verify entries are present**

```bash
grep -F "session-edits.json" .gitignore && grep -F "rules-loaded" .gitignore && grep -F ".claude/projects/" .gitignore
```

Expected: each grep prints a match.

---

## Task 4: Delete `.claude/agnets/` typo directory

**Files:**
- Delete: `.claude/agnets/` (empty directory)

- [ ] **Step 1: Verify it is empty**

```bash
ls -la .claude/agnets/
```

Expected: only `.` and `..` entries.

- [ ] **Step 2: Remove it**

```bash
rmdir .claude/agnets
```

Expected: directory removed. (`rmdir` only succeeds on empty dirs — safety net.)

- [ ] **Step 3: Verify gone**

```bash
test ! -e .claude/agnets && echo "OK"
```

Expected: `OK`.

- [ ] **Step 4: Commit C1**

```bash
git add pyproject.toml .gitignore
git status
git commit -m "chore: bootstrap Python tooling (ruff, mypy strict, pytest) + cleanup"
```

Expected: commit lands cleanly. (No source-code files in the diff.)

---

## Task 5: Rewrite ARCHITECTURE.md (Midas-style, Python/CLI)

**Files:**
- Modify: `ARCHITECTURE.md` (full rewrite)
- Source: `midas/ARCHITECTURE.md` (consult for structure)
- Spec: §6.1 row 2

- [ ] **Step 1: Read Midas ARCHITECTURE.md for structural template**

```bash
wc -l "../midas/ARCHITECTURE.md"
head -80 "../midas/ARCHITECTURE.md"
```

Expected: capture section structure: Overview → Module map → Data flow → Layering → External integrations → Folder structure.

- [ ] **Step 2: Write new ARCHITECTURE.md**

Required sections (each with real, concrete content — no placeholders):

1. **Overview** — One paragraph: algo_beta is a Python CLI that screens stocks via Finviz then runs fundamental analysis via Yahoo Finance.
2. **Module map** — Table of `fincli`, `fundainsight`, `core`, `config`, `logger` with purpose + key files.
3. **Data flow diagram (ASCII)** — Show: Click CLI → Finviz query builder → cfscrape fetch → BeautifulSoup parse → DataFrame → optional Yahoo enrichment via ThreadPoolExecutor → equity_calc → filters → CSV writer.
4. **Layering** — CLI (Click) → orchestration (`fincli/app/main.py`, `fundainsight/app/picker.py`) → calculators / utils → I/O (web_scraper, yahooquery wrapper).
5. **External integrations** — Finviz (HTML scrape via cfscrape Cloudflare bypass), Yahoo Finance (yahooquery library).
6. **Folder structure** — Tree of `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `tests/`, `workspace_output/`, `docs/`, `agents/`, `.claude/`.
7. **Threading model** — `ThreadPoolExecutor` for parallel Yahoo enrichment; logger Singleton thread-safety considerations.
8. **Configuration shape** — Pydantic `SystemSettings` base in `core/`, `Config` class in `config/config.py`, history support, JSON-driven config files.

- [ ] **Step 3: Verify file size is in the right ballpark**

```bash
wc -l ARCHITECTURE.md
```

Expected: 200–400 lines (Midas's is ~600). Don't pad; do produce real content.

- [ ] **Step 4: Spell-check / glance review**

Manual: read top to bottom for typos, broken sentences, dangling references.

---

## Task 6: Rewrite CLAUDE.md (Midas-style, ~15 KB)

**Files:**
- Modify: `CLAUDE.md` (full rewrite)
- Source: `midas/CLAUDE.md`
- Spec: §6.1 row 3

- [ ] **Step 1: Read Midas CLAUDE.md to capture structure**

```bash
wc -l "../midas/CLAUDE.md"
```

Identify sections: Project Overview, Build & Run, Architecture, File map, Conventions, MCP tool usage, Known Issues / Tech Debt.

- [ ] **Step 2: Write new CLAUDE.md**

Required sections, all concrete:

1. **Project Overview** — Identity (Fin CLI), purpose (find undervalued stocks), stack (Python 3.12+, Click, pandas, yahooquery, cfscrape, BS4, Pydantic, colorama).
2. **Build & Run** — `pip install -e ".[dev]"`, `python -m fincli`, `python -m fundainsight`, `pytest tests/`, `ruff check`, `ruff format`, `mypy`.
3. **Architecture** — One-paragraph summary pointing at ARCHITECTURE.md for detail.
4. **File map** — Table from existing CLAUDE.md + `agents/`, `docs/`, `.claude/hooks/` rows.
5. **Conventions** — Singleton logger import (`from logger import logger`), Pydantic SystemSettings base, Click command group structure, ThreadPoolExecutor for parallel I/O, timestamped CSV filenames, Google docstrings.
6. **MCP tool usage** — Same MCP tool list from `_shared-workflow.md` (sequential-thinking, memory, perplexity-ask, context7, zen).
7. **Known Issues / Tech Debt** — Carry over current list: `equity_calc.adjust_assets` `not int` truthy bug, missing tests (Phase 2 work), `wisdom_fruit/` experimental, empty scaffolds (`shared/`, `example/`, `src/`, `benchmarks/`).
8. **Phase status** — Phase 1 (this work, in progress), Phase 2 (tests), Phase 3 (coverage gate at 90%), Phase 4 (mypy warning → gate). Reference `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.

- [ ] **Step 3: Verify size and content density**

```bash
wc -c CLAUDE.md
```

Expected: roughly 12–18 KB. Aim for Midas-equivalent density without filler.

---

## Task 7: Rewrite CONTRACTS.md (CLI-focused, no REST)

**Files:**
- Modify: `CONTRACTS.md` (full rewrite)
- Source: `midas/CONTRACTS.md`
- Spec: §6.1 row 4

- [ ] **Step 1: Read Midas CONTRACTS.md for shape**

```bash
head -60 "../midas/CONTRACTS.md"
```

Capture how Midas frames "contracts as the stable surface."

- [ ] **Step 2: Write new CONTRACTS.md**

Required sections:

1. **Overview** — Contracts are the surfaces other code/users rely on remaining stable.
2. **CLI command surface** — Every Click command in `fincli/app/cli.py` and `fundainsight/app/cli.py`. Per command: name, options, defaults, exit codes (0 success / non-zero failure).
3. **Finviz query parameter contract** — The `[query_key, {value_code: display_name}]` filter shape under `fincli/resource/params/`. List every param file and its semantic group.
4. **Yahoo Finance data shape contract** — Fields read from `yahooquery.Ticker`: balance sheet line items, market cap fields, price history. Failure modes: missing field → fallback to None, ticker-not-found → row dropped.
5. **CSV output schema** — Column names, dtypes, sort order for `stock_screener_*.csv`, `funda_insight_result_*.csv`, `funda_insight_result_unfiltered_*.csv`. File naming pattern `{name}_{YYYY-MM-DD_HH-MM}.csv`.
6. **Configuration JSON shape** — Output of `core/configuration/configurator.py`; the Pydantic-validated config the CLI consumes. Top-level keys, nested structures, defaults.
7. **Logger contract** — `from logger import logger` returns a Singleton with `.info`, `.warn`, `.error`, `.debug`. Console handler types with effects (color, typing animation). File handler rotation policy. JSON handler schema.
8. **Stability policy** — Any breaking change to contracts above must (a) bump documented version, (b) be called out in commit message, (c) update CLAUDE.md tech-debt section if migration is required.

Drop all REST/HTTP/openapi/status-code language.

---

## Task 8: Rewrite README.md (public-facing, Midas-style)

**Files:**
- Modify: `README.md` (full rewrite)
- Source: `midas/README.md`
- Spec: §6.1 row 5

- [ ] **Step 1: Write new README.md**

Required sections:

1. **Title + tagline** — "Fin CLI — Stock screener + fundamental analysis."
2. **Quickstart** — Install (`pip install -e ".[dev]"`), run (`python -m fincli`, `python -m fundainsight`), output location (`workspace_output/`).
3. **Two CLI modes** — One sentence each: fincli scrapes Finviz; fundainsight enriches with Yahoo + filters.
4. **Sample output** — Show one or two CSV column headers as illustration.
5. **Configuration** — Point at `config/config.py` and CONTRACTS.md.
6. **Tests** — `pytest tests/` (note: tests still being introduced — Phase 2).
7. **Contributing (AI agents and humans)** — Read AGENTS.md first; humans also read CLAUDE.md and ARCHITECTURE.md.
8. **License + attribution** — Match existing if present.

- [ ] **Step 2: Verify it's readable top-to-bottom**

Manual: a new contributor should know how to install and run it after reading. No internal jargon without a link.

---

## Task 9: Rewrite TESTING.md (pytest, deferred coverage)

**Files:**
- Modify: `TESTING.md` (full rewrite)
- Source: `midas/TESTING.md`
- Spec: §6.1 row 6

- [ ] **Step 1: Write new TESTING.md**

Required sections:

1. **Philosophy** — Tests verify behavior, not implementation. Real fixtures over mocks where possible. Explicit Phase status: project currently has zero tests; Phase 2 introduces them.
2. **Layout** — `tests/unit/` (per-function), `tests/domain/` (per-module behavior), `tests/e2e/` (end-to-end CLI invocation, fixture-driven).
3. **Running tests** — `pytest tests/`, `pytest tests/unit/`, `pytest -k pattern`, `pytest --cov=fundainsight --cov=fincli` (informational only — no enforced threshold yet).
4. **Fixture conventions** — `conftest.py` at each test-folder root; HTML fixtures for Finviz parser; JSON fixtures for Yahoo balance-sheet shape.
5. **Mocking strategy** — `responses` or `vcrpy` for cfscrape HTTP, `unittest.mock.patch` for `yahooquery.Ticker`. Avoid mocking pandas / Pydantic — they're fast and deterministic.
6. **Coverage** — **Deferred to Phase 3** (target 90%). State this explicitly.
7. **Type checking** — `mypy fundainsight fincli core config logger` runs as part of the Stop hook quality gate. **In Phase 1 it surfaces as advisory `warnings`, not blocking `issues`.** Phase 4 promotes mypy to a hard gate once the warning count reaches zero.
8. **Lint + format** — `ruff check`, `ruff format`. Run via post-edit hook automatically; manually via the commands above.
9. **Phase 2 / Phase 3 / Phase 4 follow-up roadmap** — Cite the spec.

- [ ] **Step 2: Verify Phase 2/3/4 markers are present**

```bash
grep -i "Phase 2" TESTING.md && grep -i "Phase 3" TESTING.md && grep -i "Phase 4" TESTING.md
```

Expected: all three match. (Per AC17 from the spec.)

---

## Task 10: Create TOOLS_REFERENCE.md

**Files:**
- Create: `TOOLS_REFERENCE.md`
- Source: `midas/TOOLS_REFERENCE.md`
- Spec: §6.1 row 7

- [ ] **Step 1: Write TOOLS_REFERENCE.md**

Required sections (each is a concrete command list):

1. **Build / Run** — `pip install -e ".[dev]"`, `python -m fincli`, `python -m fundainsight`, `./run.sh`, `run.bat`.
2. **Test** — `pytest tests/`, `pytest tests/unit/`, `pytest -k <name>`, `pytest -x` (stop at first fail), `pytest -v`.
3. **Lint** — `ruff check .`, `ruff check --fix .`, `ruff check --diff .`.
4. **Format** — `ruff format .`, `ruff format --check .`.
5. **Type check** — `mypy fundainsight fincli core config logger`, `mypy --no-incremental` (clean cache).
6. **Vulnerability audit** — `pip-audit -r requirements.txt`.
7. **MCP tools** — sequential-thinking, memory, perplexity-ask, context7, zen-mcp (thinkdeep, codereview, debug). One-line description per tool.
8. **Claude Code hook reference** — Which hook fires on which event:
   - `SessionStart` → `.claude/hooks/load-rules.js` (auto-injects `agents/rules/_shared-workflow.md`, `preflight.md`, `orchestrator.md`)
   - `PreToolUse:Read` → `pre-read.js`
   - `PostToolUse:Edit|Write` → `post-edit.js` (ruff check --fix, ruff format, mypy on the saved file)
   - `Stop` → `on-stop.js` (full-repo ruff + mypy + pytest; coverage skipped Phase 3; mypy warnings-not-issues Phase 1)

---

## Task 11: Commit C2 (top-level docs)

**Files:**
- Stage: `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, `TOOLS_REFERENCE.md`

- [ ] **Step 1: Stage and verify diff**

```bash
git add ARCHITECTURE.md CLAUDE.md CONTRACTS.md README.md TESTING.md TOOLS_REFERENCE.md
git diff --staged --stat
```

Expected: 6 files in the stat (5 modifications, 1 new file).

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: rewrite top-level docs in Midas style + add TOOLS_REFERENCE"
```

Expected: clean commit. AGENTS.md is intentionally NOT in this commit — it lands last in C2 follow-up... actually keep it for C2 followup; revise: AGENTS.md is in C2 because we want it indexed alongside the other docs. (See Task 26.) For C2, just the six docs above.

Actually, per the architecture, AGENTS.md is created LAST after agents/ and docs/ exist. Defer it to C6. The commit message above stands.

---

## Task 12: Create docs/THESIS.md

**Files:**
- Create: `docs/THESIS.md`
- Source: `midas/docs/THESIS.md`
- Spec: §6.4 row 1

- [ ] **Step 1: Write docs/THESIS.md**

Required sections (drafted from existing CLAUDE.md + README.md + ARCHITECTURE.md content):

1. **Vision** — Identify undervalued stocks via two-stage pipeline (screen → fundamental analysis). Two-mode CLI: fincli (screening) + fundainsight (price-to-asset filtering).
2. **Primary user** — Yonatan Levin, personal investor, decisioning across US growth, US value, international, ADRs.
3. **Current phase** — MVP CLI working; harness in flight (Phase 1 of plan); zero tests.
4. **Roadmap (mirroring spec §8)**:
   - **Phase 1 (this work)** — Agent harness + tooling.
   - **Phase 2** — Introduce pytest test suite for `fundainsight/calculators/` + `core/`. Drive type-hint adoption.
   - **Phase 3** — Enable coverage gate at 90%.
   - **Phase 4** — Promote mypy from warnings to hard gate.
   - **Beyond Phase 4** — Make hardcoded country/sector exclusions in `picker.py` configurable; potentially add a TUI / dashboard / notebook frontend.
5. **Scope boundaries** — Not a backtest engine. Not a portfolio optimizer. Not a trading bot.
6. **Non-goals** — Real-time pricing, broker integration, paper trading.
7. **Design principles** — Calculation correctness over engineering elegance. Data sources are messy and partial — graceful degradation always. Configuration over hardcoding.

- [ ] **Step 2: Verify file landed**

```bash
test -f docs/THESIS.md && wc -l docs/THESIS.md
```

Expected: 80–200 lines.

---

## Task 13: Create docs/FEEDBACK-LOG.md and docs/MODULE_REFERENCE.md

**Files:**
- Create: `docs/FEEDBACK-LOG.md`
- Create: `docs/MODULE_REFERENCE.md`
- Source: `midas/docs/FEEDBACK-LOG.md`, `midas/docs/API_DOCUMENTATION.md`
- Spec: §6.4 rows 2–3

- [ ] **Step 1: Write docs/FEEDBACK-LOG.md**

Content:

```markdown
# FEEDBACK-LOG.md

This file captures user corrections and validations not yet promoted to durable memory.

## What goes here

- **Corrections** — User said "don't do X, do Y." Capture *why* so future sessions judge edge cases.
- **Validations** — User said "yes, that approach was right." Equally valuable — prevents drift away from approved patterns.

## Entry template

### YYYY-MM-DD — Topic

**What:** [One-line summary of the rule]

**Why:** [The reason — usually a past incident or strong preference]

**How to apply:** [When/where this guidance kicks in]

---

## Entries

(none yet)
```

- [ ] **Step 2: Write docs/MODULE_REFERENCE.md**

Required sections (one per module):

1. **`fincli/`** — Purpose: Finviz screener pipeline. Key files: `app/cli.py` (Click commands), `app/main.py` (orchestrator), `utils/web_scraper.py` (cfscrape Cloudflare bypass), `utils/quary_builders.py` (Finviz URL construction), `resource/params/` (filter parameter definitions). Public surface: CLI commands; produces `stock_screener_*.csv`. Data shapes: `pandas.DataFrame` with columns matching Finviz screener table. Error modes: cfscrape rate-limit → exponential backoff; HTML parse failure → empty DataFrame + warning. Integration: feeds fundainsight's input.
2. **`fundainsight/`** — Purpose: enrich screened stocks with Yahoo Finance + apply filters. Key files: `app/cli.py`, `app/picker.py` (orchestrator), `calculators/equity_calc.py` (price-to-asset ratios), `calculators/filters.py` (country/sector/price filters). Public surface: CLI commands; produces `funda_insight_result_unfiltered_*.csv` and `funda_insight_result_*.csv`. Data shapes: same DataFrame as fincli + appended Yahoo columns. Error modes: yahooquery missing field → None; ticker-not-found → row dropped. Integration: depends on fincli's CSV.
3. **`core/`** — Purpose: configuration framework. Key files: `configuration/config_base.py`, `configuration/configurator.py`. Public surface: `Configurator` builder class. Data shapes: Pydantic models. Error modes: validation failure → `ValidationError`. Integration: consumed by fincli + fundainsight at startup.
4. **`config/`** — Purpose: project-level Pydantic settings + history. Key files: `config.py`. Public surface: `Config` class. Integration: instantiated by core.
5. **`logger/`** — Purpose: Singleton logger with console (typing-effect colorama), file, and JSON handlers. Key files: `logger.py`, `handlers.py`, `formatters.py`, `log_cycle.py`. Public surface: `from logger import logger`. Error modes: handler init failure → fallback to bare console. Integration: imported everywhere.

---

## Task 14: Create docs/{bugs,refactoring,reviewer}/README.md + archive/ subdirs

**Files:**
- Create: `docs/bugs/README.md`, `docs/bugs/archive/.gitkeep`
- Create: `docs/refactoring/README.md`, `docs/refactoring/archive/.gitkeep`
- Create: `docs/reviewer/README.md`, `docs/reviewer/archive/.gitkeep`
- Spec: §6.4 rows 4–9

- [ ] **Step 1: Create docs/bugs/README.md**

```markdown
# Bug Tracker

This folder is a flat list of bug specs. Each bug gets one Markdown file.

## Naming

`BUG-NNN-slug.md` (e.g., `BUG-001-equity-calc-not-int-truthy.md`).

## Template

```markdown
# BUG-NNN — Title

**Date opened:** YYYY-MM-DD
**Status:** open | fixed | wontfix
**Severity:** critical | high | medium | low

## Symptom

What the user sees / what's wrong.

## Repro

Exact steps. Include CLI invocation, input data, expected vs actual.

## Root cause

Once known.

## Fix

Once known. Reference commit/PR.

## Regression test

Once written. Reference test file.
```

## Lifecycle

Open in `docs/bugs/`. When fixed and the regression test lands, move to `docs/bugs/archive/`.
```

- [ ] **Step 2: Create docs/refactoring/README.md**

```markdown
# Refactoring Specs

Cross-cutting refactor specs land here. Naming: `<topic>-spec.md`. Once shipped, move to `archive/`.

This is distinct from `docs/superpowers/specs/` which holds chronological per-feature design specs.
```

- [ ] **Step 3: Create docs/reviewer/README.md**

```markdown
# Reviewer Follow-up Tracker

Issues raised during code review that need follow-up but didn't block the merge land here. One file per issue. Naming: `<issue-tag>-<slug>.md` (e.g., `B2-prefix-match-underscore-boundary.md`).

Once the follow-up ships, move to `archive/`.
```

- [ ] **Step 4: Create empty archive markers**

```bash
touch docs/bugs/archive/.gitkeep
touch docs/refactoring/archive/.gitkeep
touch docs/reviewer/archive/.gitkeep
```

Expected: three empty files; folders are now git-trackable.

---

## Task 15: Commit C3 (docs/ tree)

**Files:**
- Stage: everything under `docs/` except the spec and plan (which are already tracked or being tracked)

- [ ] **Step 1: Stage docs tree**

```bash
git add docs/
git status
```

Expected: see `docs/THESIS.md`, `docs/FEEDBACK-LOG.md`, `docs/MODULE_REFERENCE.md`, the three subfolder READMEs, the three archive `.gitkeep`s, and (already there) `docs/superpowers/specs/2026-05-02-...md` + `docs/superpowers/plans/2026-05-02-...md`.

- [ ] **Step 2: Commit**

```bash
git commit -m "docs: scaffold docs/ tree (THESIS, FEEDBACK-LOG, MODULE_REFERENCE, subfolders)"
```

---

## Task 16: Adapt agents/rules/ (5 files)

**Files:**
- Create: `agents/rules/_shared-workflow.md`
- Create: `agents/rules/preflight.md`
- Create: `agents/rules/orchestrator.md`
- Create: `agents/rules/load-context.md`
- Create: `agents/rules/scaffold-module.md`
- Source: `midas/agents/rules/<same names>.md`
- Spec: §6.3 last 5 rows

- [ ] **Step 1: Create directories**

```bash
mkdir -p agents/rules agents/roles
```

- [ ] **Step 2: Create `agents/rules/_shared-workflow.md`**

Read `../midas/agents/rules/_shared-workflow.md`. Copy verbatim, then adapt these specific bits:

1. **MANDATORY-STEPS preamble** — keep `READ SPECS FIRST` block; same file list (`ARCHITECTURE.md`, `CONTRACTS.md`, `TESTING.md`, `AGENTS.md`).
2. **MCP tool list** — unchanged.
3. **Role table** — keep all 7 roles (ARCH, BACKEND, FRONTEND, UX_UI, VERIFIER, QA, REVIEWER). Add footnote on the table:

   > **Note:** algo_beta has no current frontend surface. Invoke FRONTEND/UX_UI only when explicitly extending the system with UI (TUI / dashboard / notebook).

4. **VERIFIER block** — flip the **coverage row from "90%" to "deferred (Phase 3)"** AND the **types/mypy row to "advisory — Phase 4 promotes to gate"**. The validation cycle ASCII art stays.
5. **Validation cycle stage description** — unchanged.

- [ ] **Step 3: Create `agents/rules/preflight.md`**

Read `../midas/agents/rules/preflight.md`. Replace Go-check items (`go vet`, `go test`, `gofmt`) with Python:

- ran `ruff check <touched module>`
- ran `mypy <touched module>` (note results may be advisory in Phase 1)
- located the relevant Click command in `app/cli.py`
- located the relevant Pydantic config in `config/config.py` or `core/configuration/`
- identified affected modules across `fincli/` / `fundainsight/` / `core/` / `config/` / `logger/`

- [ ] **Step 4: Create `agents/rules/orchestrator.md`**

Read `../midas/agents/rules/orchestrator.md`. Adapt:

- Routing logic mentions FRONTEND/UX_UI **with caveat**: "skipped by default unless the request explicitly mentions UI/TUI/dashboard/notebook output. Otherwise BACKEND covers all 'implementation' routes."
- VERIFIER block: pytest, ruff, ruff format, mypy (advisory), CSV-output schema check.
- Mode flowcharts (PLAN_AND_CREATE, EXECUTE, REFACTOR, DEBUG): keep structure; sub-step references switch from Go to Python equivalents.

- [ ] **Step 5: Create `agents/rules/load-context.md`**

Read `../midas/agents/rules/load-context.md`. Rewrite all file references:

- API change → `CONTRACTS.md` (CLI/CSV section)
- Domain-logic change → `ARCHITECTURE.md` + `fundainsight/calculators/`
- Config change → `config/config.py` + `core/configuration/configurator.py`
- New CLI command → `fincli/app/cli.py` or `fundainsight/app/cli.py` + Click conventions in `CLAUDE.md`
- Bug fix → bug spec in `docs/bugs/<BUG-NNN>.md` if applicable; otherwise root-cause via `superpowers:systematic-debugging` skill

- [ ] **Step 6: Create `agents/rules/scaffold-module.md`**

Read `../midas/agents/rules/scaffold-module.md`. Replace Go scaffolding with Python:

- Create `<module>/`, `<module>/__init__.py`, `<module>/app/cli.py`, `<module>/app/main.py`, `<module>/utils/`, optionally `<module>/resource/`.
- Test scaffolds at `tests/unit/<module>/`, `tests/domain/<module>/`, `tests/e2e/<module>/`.
- Pydantic `SystemSettings`-derived config class template.
- Click command-group template.
- Logger import: `from logger import logger`.

- [ ] **Step 7: Verify files exist + grep for Phase 4 caveats**

```bash
ls agents/rules/
grep -l "no current frontend surface" agents/rules/
grep -l "Phase 4" agents/rules/
grep -l "deferred (Phase 3)" agents/rules/
```

Expected: 5 files; `_shared-workflow.md` matches all three greps. (Per AC15.)

---

## Task 17: Adapt agents/roles/ (8 files)

**Files:**
- Create: `agents/roles/code-architect.md`, `backend-architect.md`, `frontend-developer.md`, `ui-designer.md`, `verifier.md`, `qa-debugger.md`, `code-reviewer.md`, `project-planning-handoff-specialist.md`
- Source: `midas/agents/roles/<same names>.md`
- Spec: §6.3 first 8 rows

- [ ] **Step 1: Create `agents/roles/code-architect.md`**

Copy from Midas. Adapt:
- Front-matter: keep `name: ARCH`.
- Working-style and DoD: unchanged shape.
- Replace Go conventions with: pyproject.toml, Pydantic SystemSettings, Singleton logger, Click command groups.
- Drop REST/openapi/handler vocabulary.
- Cite algo_beta files: `core/configuration/configurator.py`, `config/config.py`, `fincli/app/main.py`, `fundainsight/app/picker.py`.

- [ ] **Step 2: Create `agents/roles/backend-architect.md`**

Copy from Midas. Adapt:
- Reframe as "domain-logic architect" (no REST/DB).
- Focus: `fundainsight/calculators/`, `fundainsight/app/picker.py`, `fincli/app/main.py`.
- Reference ThreadPoolExecutor pattern, Pydantic config validation, pandas DataFrame contracts.
- Drop database/REST/auth sections.

- [ ] **Step 3: Create `agents/roles/frontend-developer.md` (HEDGE)**

Copy from Midas. Insert **prominent callout at top of body**:

```markdown
> **Status: HEDGE — No current frontend surface in algo_beta.**
> Invoke this role only when explicitly extending the system with UI: TUI, dashboard, notebook output, or interactive terminal flows.
```

Adapt content: replace web/React vocabulary with Click command groups, output formatting (colorama colored output, table formatters), terminal UX (typing-effect logger, progress indicators), CSV-to-table presentation. Keep working-style + DoD shape.

- [ ] **Step 4: Create `agents/roles/ui-designer.md` (HEDGE)**

Copy from Midas. Same `Status: HEDGE` callout. Retarget to: CLI ergonomics (option naming, defaults, `--help` text quality), error-message clarity (actionable next step), prompt design for interactive Click prompts, color/symbol conventions for `colorama`.

- [ ] **Step 5: Create `agents/roles/verifier.md`**

Copy from Midas. Adapt:
- Test-suite list rows: Unit tests (pytest), Domain tests (pytest), E2E tests (pytest with fixture data), Lint (ruff), Format (ruff format --check).
- **Types (mypy) row: "advisory only — Phase 4 promotes to gate"** (matches `_shared-workflow.md`).
- **Coverage row: "deferred (Phase 3)"**.
- CSV-output schema validation: when CSV-producing code is touched, verifier must invoke the picker on fixture data and inspect column names + dtypes. (Defer automated `--dry-run` to Phase 2; manual confirmation for Phase 1.)
- Output format unchanged (Result, Verification Summary, Test Results table, Issues Found table, Next Steps + HANDOFF_TO).

- [ ] **Step 6: Create `agents/roles/qa-debugger.md`**

Copy from Midas. Adapt:
- Severity table unchanged.
- Affected-area enum: BACKEND (any source module) | DATA (CSV / Yahoo / Finviz response) | CONFIG (Pydantic / JSON config) | UI (only if FRONTEND/UX_UI in play) | UNKNOWN.
- Repro steps must include exact CLI invocation + input flags.
- Evidence must include offending CSV row(s) when output is wrong.

- [ ] **Step 7: Create `agents/roles/code-reviewer.md`**

Copy from Midas. Adapt:
- Replace Go conventions with: PEP 8 via ruff, type hints (`from __future__ import annotations`, `typing` module), Pydantic patterns (model validators, `Field` defaults, `model_config`), **Google-style docstrings** (per spec OQ4 resolution).
- Security focus: cfscrape User-Agent leak, hardcoded API keys, CSV injection risk in `=`/`+`/`-`/`@`-prefixed strings, secret patterns from `utils.js` regexes.

- [ ] **Step 8: Create `agents/roles/project-planning-handoff-specialist.md`**

Copy from Midas verbatim. Spot-check for any Go/Midas-specific path references; replace with algo_beta equivalents if found (likely none — this role is language-neutral).

- [ ] **Step 9: Verify all 8 files exist + hedge callouts present**

```bash
ls agents/roles/ | wc -l
grep -l "Status: HEDGE" agents/roles/ | wc -l
```

Expected: `8` and `2` respectively. (Per AC2 + AC16.)

- [ ] **Step 10: Commit C4**

```bash
git add agents/
git status
git commit -m "chore: add agents/ folder (5 rules + 8 roles)"
```

---

## Task 18: Copy + adapt `.claude/hooks/utils.js`

**Files:**
- Create: `.claude/hooks/utils.js`
- Source: `midas/.claude/hooks/utils.js`
- Spec: §6.2 row 7

- [ ] **Step 1: Read Midas utils.js to understand structure**

```bash
wc -l "../midas/.claude/hooks/utils.js"
```

- [ ] **Step 2: Copy verbatim, then adapt these regions**

Copy `midas/.claude/hooks/utils.js` to `.claude/hooks/utils.js`. Then edit:

1. **`SERVICES` map** — replace with algo_beta module map:

```javascript
const SERVICES = {
    'fincli': {
        path: 'fincli/',
        runtime: 'python',
        testCommand: 'pytest tests/',
        lintCommand: 'ruff check fincli/',
        buildCommand: 'python -c "import fincli"',
        testableExtensions: ['.py'],
    },
    'fundainsight': {
        path: 'fundainsight/',
        runtime: 'python',
        testCommand: 'pytest tests/',
        lintCommand: 'ruff check fundainsight/',
        buildCommand: 'python -c "import fundainsight"',
        testableExtensions: ['.py'],
    },
    'core': {
        path: 'core/',
        runtime: 'python',
        testCommand: 'pytest tests/',
        lintCommand: 'ruff check core/',
        buildCommand: 'python -c "import core"',
        testableExtensions: ['.py'],
    },
    'config': {
        path: 'config/',
        runtime: 'python',
        testCommand: 'pytest tests/',
        lintCommand: 'ruff check config/',
        buildCommand: 'python -c "import config"',
        testableExtensions: ['.py'],
    },
    'logger': {
        path: 'logger/',
        runtime: 'python',
        testCommand: 'pytest tests/',
        lintCommand: 'ruff check logger/',
        buildCommand: 'python -c "import logger"',
        testableExtensions: ['.py'],
    },
};
```

2. **`SERVICE_DEPENDENCIES`** — replace with:

```javascript
const SERVICE_DEPENDENCIES = {
    'core': ['fincli', 'fundainsight'],
    'config': ['fincli', 'fundainsight'],
    'logger': ['fincli', 'fundainsight'],
    'fincli': ['fundainsight'],
};
```

3. **`NON_TESTABLE_PATHS`** — add algo_beta artifact paths:

```javascript
const NON_TESTABLE_PATHS = [
    'workspace_output/',
    'workspace_materials/',
    'htmlcov/',
    'dist/',
    'benchmarks/',
    '__pycache__/',
    '.pytest_cache/',
    '.mypy_cache/',
    '.ruff_cache/',
    'wisdom_fruit/',
    'shared/',
    'example/',
    'src/',
    '.venv/',
];
```

4. **`NON_TESTABLE_EXTENSIONS`** — keep Midas list; ensure `.csv`, `.pstat`, `.coverage` are present.

5. **`DOC_TRIGGER_PATTERNS`** — algo_beta-specific:

```javascript
const DOC_TRIGGER_PATTERNS = {
    'CONTRACTS.md': [
        /fincli\/resource\/params\/.*\.py$/,
        /fundainsight\/calculators\/.*\.py$/,
        /core\/configuration\/.*\.py$/,
    ],
    'ARCHITECTURE.md': [
        /fincli\/app\/main\.py$/,
        /fundainsight\/app\/picker\.py$/,
        /^[^/]+\/__main__\.py$/,
        /pyproject\.toml$/,
    ],
};
```

6. **Secret / sensitive / security regexes** — keep as-is (language-agnostic).

7. **Project-root detection, Git Bash path normalization, session tracking, `readStdin` / `respondOk` / `respondBlock`** — keep as-is.

8. **Replace any `gofmt` / `go test` / `golangci-lint` invocation** — none should exist in `utils.js`, but search and remove if any.

- [ ] **Step 3: Verify file syntactically valid**

```bash
node -c .claude/hooks/utils.js && echo "OK"
```

Expected: `OK` (file parses as JS).

- [ ] **Step 4: Verify no Go vocabulary leaked**

```bash
grep -i "go\.mod\|gofmt\|govulncheck\|golangci" .claude/hooks/utils.js
```

Expected: no matches.

---

## Task 19: Copy `.claude/hooks/load-rules.js`

**Files:**
- Create: `.claude/hooks/load-rules.js`
- Source: `midas/.claude/hooks/load-rules.js`
- Spec: §6.2 row 3

- [ ] **Step 1: Copy verbatim**

```bash
cp "../midas/.claude/hooks/load-rules.js" .claude/hooks/load-rules.js
```

- [ ] **Step 2: Verify the rule-file paths it references match our `agents/rules/` layout**

```bash
grep -E "agents/rules/" .claude/hooks/load-rules.js
```

Expected: references to `_shared-workflow.md`, `preflight.md`, `orchestrator.md`. Paths use `agents/rules/` — same layout we built. No edits needed.

- [ ] **Step 3: Syntactic validity**

```bash
node -c .claude/hooks/load-rules.js && echo "OK"
```

Expected: `OK`.

---

## Task 20: Copy `.claude/hooks/pre-read.js` (verify no Go specifics)

**Files:**
- Create: `.claude/hooks/pre-read.js`
- Source: `midas/.claude/hooks/pre-read.js`
- Spec: §6.2 row 4 (OQ2)

- [ ] **Step 1: Copy verbatim**

```bash
cp "../midas/.claude/hooks/pre-read.js" .claude/hooks/pre-read.js
```

- [ ] **Step 2: Inspect for Go-specific logic (OQ2 verification)**

```bash
grep -iE "go\.mod|gofmt|golangci|\.go['\"]\)" .claude/hooks/pre-read.js
```

Expected: no matches. If matches: replace with Python equivalents (rare; pre-read is generic).

- [ ] **Step 3: Syntactic validity**

```bash
node -c .claude/hooks/pre-read.js && echo "OK"
```

Expected: `OK`.

---

## Task 21: Retarget `.claude/hooks/post-edit.js`

**Files:**
- Create: `.claude/hooks/post-edit.js`
- Source: `midas/.claude/hooks/post-edit.js`
- Spec: §6.2 row 5

- [ ] **Step 1: Copy Midas version as starting point**

```bash
cp "../midas/.claude/hooks/post-edit.js" .claude/hooks/post-edit.js
```

- [ ] **Step 2: Locate `runLintFix` (or equivalent)**

```bash
grep -n "runLintFix\|gofmt\|gofumpt" .claude/hooks/post-edit.js
```

Note line numbers — that's the region to retarget.

- [ ] **Step 3: Replace Go branch with Python branch**

In `runLintFix`, replace the Go file-extension branch with:

```javascript
if (ext === '.py') {
    try {
        execSync(`ruff check --fix "${filePath}"`, { stdio: 'pipe', timeout: 30000 });
    } catch (e) {
        // ruff exits non-zero if findings remain after fix — that's still useful info
    }
    try {
        execSync(`ruff format "${filePath}"`, { stdio: 'pipe', timeout: 15000 });
    } catch (e) {
        // formatting failure is rare; log but don't block
    }
    try {
        execSync(`mypy "${filePath}"`, { stdio: 'pipe', timeout: 30000 });
    } catch (e) {
        // mypy errors are advisory in Phase 1 — surface in systemMessage but don't block
    }
}
```

Drop the Go branch entirely.

- [ ] **Step 4: Keep secret-scan + OWASP scan blocks unchanged**

Verify these regexes still run on the file content (they're language-agnostic). Run:

```bash
grep -n "secret\|OWASP\|sensitive" .claude/hooks/post-edit.js | head -10
```

Expected: matches still present.

- [ ] **Step 5: Verify doc-update trigger still fires**

Check `getDocUpdateNeeded` calls `DOC_TRIGGER_PATTERNS` from `utils.js`. If yes (it should), the trigger will pick up the algo_beta patterns we put in `utils.js` Task 18.

- [ ] **Step 6: Syntactic validity**

```bash
node -c .claude/hooks/post-edit.js && echo "OK"
```

Expected: `OK`.

---

## Task 22: Retarget `.claude/hooks/on-stop.js`

**Files:**
- Create: `.claude/hooks/on-stop.js`
- Create: `.claude/hooks/.gitignore`
- Source: `midas/.claude/hooks/on-stop.js`, `midas/.claude/hooks/.gitignore`
- Spec: §6.2 row 6

- [ ] **Step 1: Copy starting points**

```bash
cp "../midas/.claude/hooks/on-stop.js" .claude/hooks/on-stop.js
cp "../midas/.claude/hooks/.gitignore" .claude/hooks/.gitignore
```

- [ ] **Step 2: Locate per-service quality-gate loop**

```bash
grep -n "affectedServices\|for.*svc.*of" .claude/hooks/on-stop.js
```

Note line range.

- [ ] **Step 3: Replace per-service loop with single repo-level block**

The single block runs:

```javascript
const qualityChecks = [
    {
        name: 'Lint (ruff)',
        cmd: 'ruff check .',
        channel: 'issues', // ruff failures block
    },
    {
        name: 'Format (ruff format --check)',
        cmd: 'ruff format --check .',
        channel: 'issues',
    },
    {
        name: 'Type check (mypy)',
        cmd: 'mypy fundainsight fincli core config logger',
        channel: 'warnings', // Phase 1: advisory only. Phase 4 flips to 'issues'.
    },
    {
        name: 'Tests (pytest)',
        cmd: 'pytest tests/',
        channel: 'issues',
    },
];

for (const check of qualityChecks) {
    const result = runCommand(check.cmd, { timeout: 300000 });
    if (!result.success) {
        if (check.channel === 'issues') {
            issues.push({ name: check.name, output: result.output });
        } else {
            warnings.push({ name: check.name, output: result.output });
        }
    }
}
```

(Adapt to the actual variable names + helper functions in the Midas source. The principle is: **mypy goes through `warnings`, not `issues`, in Phase 1.**)

- [ ] **Step 4: Stub `runCoverageCheck`**

Replace its body with:

```javascript
function runCoverageCheck() {
    return {
        skipped: true,
        reason: 'Phase 3 deferred — no coverage threshold yet',
    };
}
```

- [ ] **Step 5: Replace dependency audit (govulncheck → pip-audit)**

In `runDependencyAudit` (or equivalent):

```javascript
function runDependencyAudit() {
    try {
        execSync('pip-audit -r requirements.txt', { stdio: 'pipe', timeout: 60000 });
        return { success: true };
    } catch (e) {
        if (e.code === 'ENOENT' || /not found/i.test(e.message)) {
            return { success: true, note: 'pip-audit not installed, skipping vulnerability audit' };
        }
        return { success: false, output: e.stdout?.toString() || e.message };
    }
}
```

- [ ] **Step 6: Drop TypeScript-specific branches**

```bash
grep -in "typescript\|\.ts['\"]\)" .claude/hooks/on-stop.js
```

Expected: any matches were inherited from Midas template. Remove unconditionally. Re-grep to confirm no matches remain.

- [ ] **Step 7: Keep skill reminders**

```bash
grep -n "/docs-update\|/github-tracking" .claude/hooks/on-stop.js
```

Expected: matches present. Don't touch them.

- [ ] **Step 8: Syntactic validity**

```bash
node -c .claude/hooks/on-stop.js && echo "OK"
```

Expected: `OK`.

- [ ] **Step 9: Commit C5**

```bash
git add .claude/hooks/
git status
git commit -m "feat: wire .claude/ hook harness (load-rules, pre-read, post-edit, on-stop, utils)"
```

---

## Task 23: Create AGENTS.md (last among docs — indexes everything)

**Files:**
- Create: `AGENTS.md`
- Source: `midas/AGENTS.md`
- Spec: §6.1 row 1

- [ ] **Step 1: Read Midas AGENTS.md as structural template**

```bash
wc -l "../midas/AGENTS.md"
```

- [ ] **Step 2: Write AGENTS.md**

Required structure:

1. **Header preamble** — "If you are an AI agent opening this repository, **start here**." Include the principle: *If it's not written to a file, it doesn't exist.*

2. **Loading Order (Tier 1–4)**:

   **Tier 1 — Identity & Direction (always read)**
   | # | File | Purpose |
   |---|---|---|
   | 1 | `CLAUDE.md` | Project identity, tech stack, conventions, important files |
   | 2 | `AGENTS.md` (this file) | Loading contract |
   | 3 | `docs/THESIS.md` | Product direction, current phase, roadmap |

   **Tier 2 — Working Memory (read when resuming work)**
   | # | File | Purpose |
   |---|---|---|
   | 4 | `.claude/projects/<project-hash>/memory/MEMORY.md` | Durable memory index |
   | 5 | `docs/FEEDBACK-LOG.md` | User corrections + validations not yet promoted |
   | 6 | `.claude/projects/<project-hash>/memory/daily/YYYY-MM-DD.md` | Today's session notes |

   **Tier 3 — Operational Rules (read when acting in a specific role)**
   | # | File | Purpose |
   |---|---|---|
   | 7 | `agents/rules/_shared-workflow.md` | Shared workflow (auto-loaded by `.claude/hooks/load-rules.js`) |
   | 8 | `agents/rules/preflight.md` | Pre-implementation checklist (auto-loaded) |
   | 9 | `agents/rules/orchestrator.md` | Routing logic (auto-loaded) |
   | 10 | `agents/rules/<mode>.md` | Mode-specific rules (load-context, scaffold-module) |
   | 11 | `agents/roles/<role>.md` | Role-specific rules (BACKEND/ARCH/QA/REVIEWER/VERIFIER/FRONTEND/UX_UI/PROJECT-PLANNING) |

   **Tier 4 — Task-Specific Deep Dive**
   | # | File | Purpose |
   |---|---|---|
   | 12 | `docs/MODULE_REFERENCE.md` | Per-module reference |
   | 13 | `CONTRACTS.md` | Stable surfaces (CLI, CSV, Yahoo/Finviz, config) |
   | 14 | `ARCHITECTURE.md` | System architecture, data flow |
   | 15 | `TESTING.md` | Test layout, conventions, deferred coverage |
   | 16 | `TOOLS_REFERENCE.md` | Build / run / lint / format / type / pytest / MCP / hook reference |
   | 17 | `docs/superpowers/specs/` | Per-feature design specs |
   | 18 | `docs/superpowers/plans/` | Implementation plans |
   | 19 | `docs/bugs/` | Bug specs |
   | 20 | `docs/refactoring/` | Cross-cutting refactor specs |
   | 21 | `docs/reviewer/` | Review follow-up tracker |
   | 22 | `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/` | Source code |

3. **File Roles (Quick Reference)** — table mapping Identity / Direction / Durable memory / Volatile preferences / Daily notes / Operational rules / Reference docs to lifecycle.

4. **When to Write to These Files** — write to `MEMORY.md` (durable), `FEEDBACK-LOG.md` (corrections + validations), daily notes (session findings), `docs/THESIS.md` (direction).

5. **Curation Rhythm** — per-session / end-of-session / weekly / per-phase.

6. **Sub-Agent Context Diet** — sub-agents receive only task prompt + relevant role file + needed file paths. Do NOT inject full Tier 1–4.

7. **What This File Is NOT** — not a tutorial, not a personality guide, not a replacement for `agents/rules/`.

8. **How Claude Code Auto-Loads Tier 3 Rules** — `.claude/hooks/load-rules.js` reads `_shared-workflow.md`, `preflight.md`, `orchestrator.md` on every `SessionStart`. The other rules (`load-context.md`, `scaffold-module.md`) are read on-demand.

9. **Change Log** — initial entry: `2026-05-02 | Initial file. Mirrored from Midas v2026-05-01. Retargeted Go→Python, REST→CLI, observability/valuation refs replaced with module/calculator refs.`

- [ ] **Step 3: Verify every Tier 1–4 file path resolves**

```bash
for f in CLAUDE.md AGENTS.md docs/THESIS.md docs/FEEDBACK-LOG.md \
         agents/rules/_shared-workflow.md agents/rules/preflight.md agents/rules/orchestrator.md \
         agents/rules/load-context.md agents/rules/scaffold-module.md \
         docs/MODULE_REFERENCE.md CONTRACTS.md ARCHITECTURE.md TESTING.md TOOLS_REFERENCE.md \
         docs/bugs/README.md docs/refactoring/README.md docs/reviewer/README.md; do
    test -f "$f" || echo "MISSING: $f"
done
```

Expected: no `MISSING:` lines.

```bash
test -d agents/roles && ls agents/roles/ | wc -l
test -d docs/superpowers/specs && ls docs/superpowers/specs/
test -d docs/superpowers/plans && ls docs/superpowers/plans/
```

Expected: 8 roles; specs dir contains the design spec; plans dir contains this plan.

---

## Task 24: Create `.claude/settings.json` + merge `settings.local.json`

**Files:**
- Create: `.claude/settings.json`
- Modify: `.claude/settings.local.json`
- Source: `midas/.claude/settings.json`, `midas/.claude/settings.local.json`
- Spec: §6.2 rows 1–2

- [ ] **Step 1: Create settings.json**

Content (mirrors Midas exactly — no algo_beta-specific tweaks):

```json
{
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
    "hooks": {
        "SessionStart": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/load-rules.js\"",
                        "timeout": 10,
                        "statusMessage": "Loading workflow rules..."
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "Read",
                "hooks": [
                    {
                        "type": "command",
                        "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/pre-read.js\"",
                        "timeout": 10,
                        "statusMessage": "Running pre-read quality checks..."
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Edit|Write",
                "hooks": [
                    {
                        "type": "command",
                        "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/post-edit.js\"",
                        "timeout": 60,
                        "statusMessage": "Running post-edit quality checks..."
                    }
                ]
            }
        ],
        "Stop": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "node \"$CLAUDE_PROJECT_DIR/.claude/hooks/on-stop.js\"",
                        "timeout": 600,
                        "statusMessage": "Running quality gates..."
                    }
                ]
            }
        ]
    }
}
```

- [ ] **Step 2: Read existing settings.local.json**

```bash
cat .claude/settings.local.json
```

Note current content for merge.

- [ ] **Step 3: Merge in Python permissions**

Edit `.claude/settings.local.json` to include (preserve any existing entries; add these):

```json
{
    "permissions": {
        "allow": [
            "Bash(python:*)",
            "Bash(python -m:*)",
            "Bash(pytest:*)",
            "Bash(ruff:*)",
            "Bash(mypy:*)",
            "Bash(pip:*)",
            "Bash(pip-audit:*)",
            "Bash(git:*)"
        ]
    }
}
```

(If the existing file already has a `permissions.allow` list, **merge** rather than replace. Use a JSON-aware approach.)

- [ ] **Step 4: Verify both files parse as valid JSON**

```bash
node -e "JSON.parse(require('fs').readFileSync('.claude/settings.json'))" && echo "settings.json OK"
node -e "JSON.parse(require('fs').readFileSync('.claude/settings.local.json'))" && echo "settings.local.json OK"
```

Expected: two `OK` lines.

---

## Task 25: End-to-end validation (V1–V12)

**Files:**
- None modified — this is a verification pass

- [ ] **Step 1: V11 — Smoke import**

```bash
python -c "import fincli; import fundainsight"
```

Expected: no error. Confirms no source code broke during the harness work (it shouldn't have — we didn't touch source).

- [ ] **Step 2: V9 — ruff baseline**

```bash
ruff check . | tail -3
```

Expected: a finding count. Phase 1 baseline; record for tracking.

- [ ] **Step 3: V10 — mypy strict baseline**

```bash
mypy fundainsight fincli core config logger 2>&1 | tail -3
```

Expected: many errors (hundreds). The override block silences `cfscrape`/`yahooquery` `import-untyped` errors. Non-override errors are the Phase 4 starting baseline.

- [ ] **Step 4: V12 — git status sanity**

```bash
git status --short
git diff --name-only HEAD~5..HEAD | grep -E "^(fincli|fundainsight|core|config|logger|scripts|wisdom_fruit|shared|example|src)/" || echo "no source changes"
```

Expected: `no source changes` printed. (No source files touched in any of C0-C5.)

- [ ] **Step 5: V7 — every AGENTS.md tier file resolves**

```bash
# Already done in Task 23 Step 3, re-run for sanity:
for f in CLAUDE.md AGENTS.md docs/THESIS.md docs/FEEDBACK-LOG.md \
         agents/rules/_shared-workflow.md agents/rules/preflight.md agents/rules/orchestrator.md \
         agents/rules/load-context.md agents/rules/scaffold-module.md \
         docs/MODULE_REFERENCE.md CONTRACTS.md ARCHITECTURE.md TESTING.md TOOLS_REFERENCE.md; do
    test -f "$f" || echo "MISSING: $f"
done
```

Expected: no `MISSING:` lines.

- [ ] **Step 6: V8 — _shared-workflow.md hedge note + Phase 4 mypy text**

```bash
grep -F "no current frontend surface" agents/rules/_shared-workflow.md && \
grep -F "Phase 4" agents/rules/_shared-workflow.md && \
grep -F "deferred (Phase 3)" agents/rules/_shared-workflow.md
```

Expected: all three match. (Per AC15.)

- [ ] **Step 7: V1 — Open a fresh Claude Code session in a separate terminal**

Manual step — outside this plan-execution flow. Confirm `SessionStart` hook fires; the user sees `# Loaded Workflow Rules (agents/rules/)` block with content from `_shared-workflow.md`/`preflight.md`/`orchestrator.md`.

If it doesn't fire: check `.claude/settings.json` is valid JSON; `node "$CLAUDE_PROJECT_DIR/.claude/hooks/load-rules.js"` runs by hand and returns content.

- [ ] **Step 8: V2 — Save a `.py` file (no real edit needed; just touch + save in editor)**

Manual step. Touch any `.py` file. Confirm `post-edit.js` fires; surfaces lint/format/mypy result. Mypy errors should appear as `systemMessage` warnings, not blocking issues.

- [ ] **Step 9: V5 — Trigger Stop event**

Manual step. End the Claude Code session (or trigger `Stop`). Confirm `on-stop.js` runs ruff + mypy + pytest. Mypy block surfaces under `warnings`, NOT `issues`. Coverage block reports `skipped: true, reason: 'Phase 3 deferred'`.

- [ ] **Step 10: V6 — Sub-agent dispatch**

Manual step. Open a fresh Claude Code session and request the user to dispatch ARCH (`/agents/roles/code-architect.md`) on a trivial task. Confirm sub-agent works with Python/algo_beta vocabulary, not Go/Midas.

---

## Task 26: Final commit + PR readiness

**Files:**
- Stage: any remaining unstaged work

- [ ] **Step 1: Stage AGENTS.md and settings**

```bash
git add AGENTS.md .claude/settings.json .claude/settings.local.json
git status
```

Expected: AGENTS.md, settings.json, settings.local.json staged. Anything else? Investigate.

- [ ] **Step 2: Commit C6**

```bash
git commit -m "chore: add AGENTS.md loading contract + wire .claude/settings.json"
```

- [ ] **Step 3: Verify the full set of commits**

```bash
git log --oneline -8
```

Expected:
```
<sha> chore: add AGENTS.md loading contract + wire .claude/settings.json
<sha> feat: wire .claude/ hook harness (load-rules, pre-read, post-edit, on-stop, utils)
<sha> chore: add agents/ folder (5 rules + 8 roles)
<sha> docs: scaffold docs/ tree (THESIS, FEEDBACK-LOG, MODULE_REFERENCE, subfolders)
<sha> docs: rewrite top-level docs in Midas style + add TOOLS_REFERENCE
<sha> chore: bootstrap Python tooling (ruff, mypy strict, pytest) + cleanup
<sha> chore: snapshot pre-rewrite top-level docs as baseline
<sha> ... (master tip)
```

- [ ] **Step 4: Push and prepare PR**

```bash
git push -u origin feat/agent-harness
```

Expected: branch pushed. Open a PR titled `feat: replicate Midas agent harness in algo_beta (Phase 1)` with description pointing at `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.

- [ ] **Step 5: Acceptance criteria self-check (AC1–AC19 from spec §14)**

Walk through every AC in the spec; confirm each one is satisfied. Record any gap → either fix in this PR or open a follow-up issue. (Most ACs are mechanical greps from this plan's commands; manually re-run if anything is uncertain.)

---

## Self-Review (executed before handoff)

**Spec coverage check:**
- §6.1 (top-level docs, 7 files) → Tasks 5–11 + 23 ✓
- §6.2 (.claude/ harness, 9 entries) → Tasks 4, 18–22, 24 ✓
- §6.3 (agents/, 13 files) → Tasks 16–17 ✓
- §6.4 (docs/, 11 entries) → Tasks 12–14, 15 (commit) ✓
- §6.5 (cross-cutting: pyproject, .gitignore, NOT-touched) → Tasks 1–4 + verification in 25 ✓
- §7 (tooling) → Task 1 (config) + Task 25 V9/V10 (validation) ✓
- §8 (phased follow-ups) → Phase markers planted in CLAUDE.md (T6), TESTING.md (T9), THESIS.md (T12), `_shared-workflow.md` (T16), `verifier.md` (T17 step 5), `on-stop.js` `runCoverageCheck` stub (T22 step 4) ✓
- §9 (FRONTEND/UX_UI hedge) → Task 17 steps 3–4 (HEDGE callouts) + Task 16 step 2 (`_shared-workflow.md` footnote) + AC16 in T26 step 5 ✓
- §10 (out of scope) → guard rails in T26 step 5 (V12 git diff check) ✓
- §11 (V1–V12) → Task 25 ✓
- §14 (AC1–AC19) → Task 26 step 5 ✓

**Placeholder scan:** none. Every task has either concrete commands or concrete content templates.

**Type / signature consistency:** the `SERVICES` map in T18, the `qualityChecks` array in T22, and the override list in T1 all reference the same module names (`fundainsight`, `fincli`, `core`, `config`, `logger`). The `runtime: 'python'` value in T18's SERVICES map matches the Python tooling everywhere else.

---

## Phase 1 Done When

All 6 commits land on `feat/agent-harness`. Validation V1–V12 passes (manual steps + automated greps). PR opened with a one-paragraph description and a checked AC1–AC19 list.

Phase 2 (introduce pytest tests + drive type-hint adoption) opens immediately after.
