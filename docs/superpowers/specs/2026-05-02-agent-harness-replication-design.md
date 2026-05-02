# Algo Beta Agent Harness Replication — Design Specification

**Version:** 0.1 DRAFT
**Date:** 2026-05-02
**Status:** DESIGN
**Author:** yonatan
**Mode:** REFACTOR (cross-cutting tooling/process change; zero source-code changes)
**Builds on:** Midas DCF Valuation API agent harness (`C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\`)

---

## 1. Summary

Replicate the full Midas agent harness — the AGENTS.md loading contract, `.claude/` hooks, `agents/roles/` + `agents/rules/` ruleset, and `docs/` tree (THESIS.md, FEEDBACK-LOG.md, MODULE_REFERENCE.md, bugs/refactoring/reviewer/superpowers folders) — in `algo_beta`, retargeted from Go/REST to Python/CLI semantics. Ship the change as a single coordinated PR because the artifacts cross-reference each other (AGENTS.md cites `docs/` paths; hooks cite `agents/rules/`; rules reference `ARCHITECTURE.md` / `CONTRACTS.md` / `TESTING.md`). Source code under `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `scripts/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`, plus `requirements.txt` and existing tests, are out of scope.

---

## 2. Goals and Non-Goals

### Goals

- **G1** Every Tier 1–4 file referenced by `AGENTS.md` exists in `algo_beta` and is reachable at the cited path.
- **G2** A new Claude Code session in `algo_beta` triggers the `SessionStart` hook, which loads `_shared-workflow.md`, `preflight.md`, and `orchestrator.md` from `agents/rules/` into context, identical in shape to the Midas behavior.
- **G3** A `.py` save fires the `PostToolUse:Edit|Write` hook and runs `ruff check --fix`, `ruff format`, and `mypy <file>` against the saved file. A test-runner step is best-effort and only fires when a matching test exists (Phase 2+).
- **G4** `Stop` hook runs the full repo-level Python quality gate: `ruff check .`, `ruff format --check .`, `mypy fundainsight/ fincli/ core/ config/`, `pytest tests/`. **Coverage gate is intentionally absent** in this phase (see §8).
- **G5** All seven top-level docs (`AGENTS.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, `TOOLS_REFERENCE.md`) match the Midas style and depth, retargeted to Python and CLI semantics — not Go and REST.
- **G6** All eight role files and five rule files in `agents/` are Python/CLI-aware. `FRONTEND` and `UX_UI` roles are retained per explicit user direction (§9) but flagged as "no current frontend surface."
- **G7** `pyproject.toml` is updated with `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`, `[tool.mypy]`, `[tool.pytest.ini_options]` configuration sections, plus a dev dependency group (`ruff`, `mypy`, `pytest`). The stale `yfinance` runtime dep is replaced with `yahooquery` to match real code usage.
- **G8** `.gitignore` excludes hook session-state files (`.claude/hooks/.session-edits.json`, `.claude/hooks/.rules-loaded`, `.claude/projects/`).
- **G9** Zero source-code changes. No edits to `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `scripts/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`, `requirements.txt`, or any existing tests.

### Non-Goals

- **N1** Introducing actual pytest tests under `tests/`. That is Phase 2 follow-up (§8).
- **N2** Enforcing a coverage threshold in `on-stop.js`. That is Phase 3 follow-up (§8).
- **N3** Fixing tech debt called out in the existing `CLAUDE.md` (e.g., the `not int` truthy bug in `equity_calc.adjust_assets`, the `wisdom_fruit/` experiment, empty scaffolding folders). Those become entries in the rewritten `CLAUDE.md` "Known Issues" section and may seed `docs/bugs/` entries, but they are not fixed here.
- **N4** Building any TUI / dashboard / notebook UI on top of `fundainsight`. The `FRONTEND`/`UX_UI` roles are kept as a hedge (§9), not implemented.
- **N5** Porting Midas-specific docs (`docs.go`, `openapi.yaml`, `swagger.json`, `swagger.yaml`, `postman_collection.json`, `integration/` archive, `sec_data_cleaning_guide.md`, `columns name.txt`). algo_beta has no REST API and no SEC EDGAR pipeline, so these have no analogue (§6.4).
- **N6** Updating `requirements.txt` runtime dependencies. The runtime stack is unchanged.
- **N7** Wiring CI / GitHub Actions for the new Python tooling. The hooks run locally; CI integration is out of scope and would be a follow-up.

---

## 3. Background

### 3.1 What `algo_beta` is today

`algo_beta` is a Python 3.12+ CLI tool, not a REST service. Two main modules:

- `fincli/` — scrapes Finviz.com via `cfscrape` (Cloudflare bypass) and `BeautifulSoup4`, parses screener tables into `pandas` DataFrames, writes timestamped CSVs to `workspace_output/`.
- `fundainsight/` — enriches screened tickers via `yahooquery` (Yahoo Finance), computes price-to-asset ratios in `fundainsight/calculators/equity_calc.py`, applies country/sector/price filters in `fundainsight/calculators/filters.py`, writes filtered CSVs.

Supporting modules:
- `core/` — base configuration classes, JSON converters.
- `config/` — Pydantic `BaseModel` settings with history support.
- `logger/` — Singleton (metaclass-based) logger with console/file/JSON handlers.

Tech stack: Python 3.12+, `click` (CLI), `pandas`, `yahooquery`, `cfscrape`, `BeautifulSoup4`, `pydantic`, `colorama`. No web framework, no database, no REST surface.

### 3.2 What exists in `algo_beta` today (relevant to this work)

- Top-level docs: `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md` — present but pre-Midas-style; will be **REWRITTEN** in this work.
- `.claude/`:
  - `settings.local.json` — present, will be **MERGED** with new permissions.
  - `agnets/` (typo folder) — empty, will be **DELETED**.
  - `hooks/` — empty (no scripts present).
  - `worktrees/` — present, untouched.
- `pyproject.toml` — barebones (`[project]` + dependencies only). No tooling config. Contains stale `yfinance` dep (code uses `yahooquery`).
- `requirements.txt` — runtime-only, untouched in this work.
- `tests/` — `unit/`, `domain/`, `e2e/` subfolders exist; only `__pycache__` survives — no actual test files.
- `.gitignore` — already modified (status `M`); will get one targeted edit.

### 3.3 What is missing vs. Midas

- `AGENTS.md` (Tier 1–4 loading contract).
- `TOOLS_REFERENCE.md`.
- The entire `docs/` tree (THESIS.md, FEEDBACK-LOG.md, MODULE_REFERENCE.md, bugs/, refactoring/, reviewer/, superpowers/).
- The entire `agents/` folder (roles/ + rules/).
- All `.claude/hooks/*.js` scripts.
- `.claude/settings.json` (the wired hook entry points).
- Tooling config in `pyproject.toml` (`ruff`, `mypy`, `pytest`).

### 3.4 Language / architecture mismatch with Midas

| Dimension | Midas | algo_beta |
|---|---|---|
| Language | Go 1.23+ | Python 3.12+ |
| Surface | REST API (Gin) | CLI (Click) |
| Architecture | Clean / Hexagonal with `uber/fx` DI | Layered modules + Pydantic config + Singleton logger |
| Data sources | SEC EDGAR + Yahoo + Finzive + FRED | Finviz (HTML scrape) + Yahoo (yahooquery) |
| Output | JSON over HTTP | CSVs in `workspace_output/` |
| Test framework | `go test`, `go vet`, `govulncheck` | `pytest`, `ruff`, `mypy` |
| Auto-formatter | `gofmt` | `ruff format` |
| API contract | OpenAPI / Swagger | CLI command surface + CSV schema + JSON config schema |
| Coverage | 90% threshold enforced | None today; deferred (Phase 3) |
| Existing tests | Extensive | None |

Every Midas artifact must be retargeted along these axes, not merely copy/pasted.

---

## 4. Approach

**Single-PR full mirror, retargeted.** All harness pieces ship as one cohesive change because:

- `AGENTS.md` references files in `docs/`, `agents/rules/`, `agents/roles/`, and `.claude/hooks/`. Shipping any subset would leave dangling references.
- `_shared-workflow.md` references `ARCHITECTURE.md`, `CONTRACTS.md`, `TESTING.md`, `AGENTS.md`. Rewriting any of those without the rest produces inconsistent vocabulary.
- `load-rules.js` reads `agents/rules/*.md`; `on-stop.js` runs `ruff`/`mypy`/`pytest` configured in `pyproject.toml`; `post-edit.js` references doc-update triggers documented in `CLAUDE.md`. The hooks and the docs are mutually load-bearing.

The implementation is mechanical once the spec is settled. The implementer reads each Midas source file, applies the retarget rules in §6, and writes the algo_beta equivalent — no design left undone.

Phasing for follow-up work (tests + coverage) is captured in §8.

---

## 5. Architecture (high-level structure)

After this work, the `algo_beta` root will look like:

```
algo_beta/
├── AGENTS.md                          # NEW — loading contract (Tier 1-4)
├── ARCHITECTURE.md                    # REWRITE — fincli → fundainsight pipeline
├── CLAUDE.md                          # REWRITE — Midas-style, ~15 KB, Python/CLI
├── CONTRACTS.md                       # REWRITE — CLI surface + CSV schema + Yahoo/Finviz contracts
├── README.md                          # REWRITE — public-facing quickstart
├── TESTING.md                         # REWRITE — pytest layout, ruff, mypy, deferred coverage
├── TOOLS_REFERENCE.md                 # NEW — all CLI commands + MCP tools + Claude Code hooks
├── pyproject.toml                     # EDIT — add ruff/mypy/pytest config + dev deps
├── .gitignore                         # EDIT — ignore hook state files
├── .claude/
│   ├── settings.json                  # NEW — hook wiring identical to Midas
│   ├── settings.local.json            # MERGE — preserve current + add Python/git/pytest perms
│   └── hooks/
│       ├── .gitignore                 # NEW (copy)
│       ├── load-rules.js              # COPY (verify path-portable)
│       ├── pre-read.js                # COPY (verify no Go-specific logic)
│       ├── post-edit.js               # RETARGET — replace gofmt with ruff/mypy
│       ├── on-stop.js                 # RETARGET — Python tooling, NO coverage gate
│       └── utils.js                   # ADAPT — replace SERVICES map with Python module map
├── agents/                            # NEW — top-level (mirrors Midas)
│   ├── roles/
│   │   ├── code-architect.md          # ADAPT — Python conventions
│   │   ├── backend-architect.md       # ADAPT — domain-logic architect (no REST/DB)
│   │   ├── frontend-developer.md      # KEEP & ADAPT — Click/colorama hedge
│   │   ├── ui-designer.md             # KEEP & ADAPT — CLI ergonomics hedge
│   │   ├── verifier.md                # ADAPT — pytest/ruff/mypy + CSV schema validation
│   │   ├── qa-debugger.md             # ADAPT — CLI E2E on fixture data
│   │   ├── code-reviewer.md           # ADAPT — Python idioms, type hints, Pydantic
│   │   └── project-planning-handoff-specialist.md  # COPY (language-neutral)
│   └── rules/
│       ├── _shared-workflow.md        # ADAPT — role table notes "no current frontend surface"
│       ├── preflight.md               # ADAPT — Python checklist
│       ├── orchestrator.md            # ADAPT — routing notes FRONTEND/UX_UI caveat
│       ├── load-context.md            # ADAPT — algo_beta file references
│       └── scaffold-module.md         # ADAPT — __init__.py, Pydantic config, Click groups
└── docs/                              # NEW tree
    ├── THESIS.md                      # NEW — drafted from existing README/CLAUDE/ARCHITECTURE
    ├── FEEDBACK-LOG.md                # NEW — empty template
    ├── MODULE_REFERENCE.md            # NEW — algo_beta's analogue to Midas API_DOCUMENTATION.md
    ├── bugs/
    │   ├── README.md                  # NEW — explains BUG-NNN-slug.md format
    │   └── archive/                   # NEW (empty)
    ├── refactoring/
    │   ├── README.md                  # NEW
    │   └── archive/                   # NEW (empty)
    ├── reviewer/
    │   ├── README.md                  # NEW
    │   └── archive/                   # NEW (empty)
    └── superpowers/
        ├── specs/
        │   └── 2026-05-02-agent-harness-replication-design.md   # THIS FILE
        └── plans/                     # NEW (empty, future plans land here)
```

**Cross-reference graph (must remain consistent):**

```
AGENTS.md ──► CLAUDE.md, docs/THESIS.md, docs/FEEDBACK-LOG.md,
              agents/rules/{_shared-workflow,preflight,orchestrator,load-context,scaffold-module}.md,
              agents/roles/*.md,
              docs/MODULE_REFERENCE.md, docs/superpowers/specs/, docs/reviewer/, docs/bugs/

.claude/settings.json ──► .claude/hooks/{load-rules,pre-read,post-edit,on-stop}.js
.claude/hooks/load-rules.js ──► agents/rules/{_shared-workflow,preflight,orchestrator}.md
.claude/hooks/utils.js ──► fincli/, fundainsight/, core/, config/, logger/ (path detection)
.claude/hooks/post-edit.js ──► utils.js, ARCHITECTURE.md/CONTRACTS.md (doc-update triggers)
.claude/hooks/on-stop.js ──► utils.js + pyproject.toml (tool config)

agents/rules/_shared-workflow.md ──► ARCHITECTURE.md, CONTRACTS.md, TESTING.md, AGENTS.md, agents/roles/*.md
agents/rules/orchestrator.md ──► agents/roles/*.md
```

---

## 6. Detailed Design

### 6.1 Section 1 — Top-level docs (7 files)

| File | Action | Midas source path | Retain | Retarget |
|---|---|---|---|---|
| `AGENTS.md` | NEW | `midas/AGENTS.md` | Tier 1–4 structure, "if not written to a file it doesn't exist" principle, Sub-Agent Context Diet, Curation Rhythm, change log scaffold | All paths and entries: Tier 1 → `CLAUDE.md` + `AGENTS.md` + `docs/THESIS.md`. Tier 4 entries replace Midas observability/valuation specs with algo_beta items: `docs/MODULE_REFERENCE.md`, `docs/superpowers/specs/`, `docs/reviewer/`, `docs/bugs/`, and `fincli/`/`fundainsight/` source paths. Drop the `internal/observability/` line entirely. |
| `ARCHITECTURE.md` | REWRITE | `midas/ARCHITECTURE.md` | Section structure: Overview, Module map, Data flow diagram, Layering, External integrations, Folder structure | Replace clean/hexagonal/`uber/fx` with the layered Python module structure. Data flow: Finviz query → cfscrape fetch → BeautifulSoup parse → DataFrame → optional Yahoo enrichment via ThreadPoolExecutor → equity_calc + filters → CSV. Folder tree: `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`. Layering: CLI (Click) → orchestration (`fincli/app/main.py`, `fundainsight/app/picker.py`) → calculators / utils → I/O (web_scraper, yahooquery wrapper). |
| `CLAUDE.md` | REWRITE | `midas/CLAUDE.md` | Section structure: Project Overview, Build & Run Commands, Architecture, Quick file map, Conventions, MCP tool usage notes, Known Issues / Tech Debt | All content. Identity: Fin CLI. Stack: Python 3.12+ / Click / pandas / yahooquery / cfscrape / BS4 / Pydantic / colorama. Build/Run: `python -m fincli`, `python -m fundainsight`, `pytest tests/`, `ruff check`, `ruff format`, `mypy fundainsight/`. File map: from existing CLAUDE.md table. Conventions: Singleton logger import, Pydantic `SystemSettings` base, Click command groups, parallel `ThreadPoolExecutor` enrichment, timestamped CSV filenames. Known Issues: pyproject `yfinance`/`yahooquery` drift (resolved by this work), missing tests (Phase 2), `equity_calc.adjust_assets` `not int` bug, empty scaffolds (`shared/`, `example/`, `src/`), experimental `wisdom_fruit/`. **Target size ~15 KB**, expanded from current ~4 KB to match Midas density. |
| `CONTRACTS.md` | REWRITE | `midas/CONTRACTS.md` | Concept that contracts are the stable surface other code/users depend on; section structure | algo_beta has **no REST API**. The contracts are: (a) **CLI command surface** — every Click command, its options, exit codes; (b) **Finviz query parameter contract** — the `[query_key, {value_code: display_name}]` filter shape under `fincli/resource/params/`; (c) **Yahoo Finance data shape contract** — the fields read from `yahooquery` (balance sheet line items, market cap fields, price history) and the failure modes when fields are missing; (d) **CSV output schema** — column names, types, sort order, file naming pattern `{name}_{YYYY-MM-DD_HH-MM}.csv`; (e) **Configuration JSON shape** — the Pydantic-validated config produced by `core/configuration/configurator.py`. Drop all REST/HTTP/status-code language. |
| `README.md` | REWRITE | `midas/README.md` | Public-facing tone, badges, quickstart, contributing pointer to AGENTS.md | Install via `pip install -r requirements.txt`. Two CLI modes (`python -m fincli`, `python -m fundainsight`). Output samples (CSV column shapes). Link to `docs/THESIS.md` for direction and `AGENTS.md` for AI-agent contributors. Link to `TESTING.md` for test conventions. |
| `TESTING.md` | REWRITE | `midas/TESTING.md` | Philosophy section, test categories, fixture conventions, test naming, "running tests" command list | Retarget to `pytest`. Layout: `tests/unit/`, `tests/domain/`, `tests/e2e/` (preserve existing folders). Mocking strategy: `responses`/`vcrpy` for cfscrape HTTP, `unittest.mock` for `yahooquery.Ticker`. Fixtures: HTML samples for Finviz parser, JSON fixtures for Yahoo balance-sheet shape. Commands: `pytest tests/`, `pytest tests/unit/`, `pytest -k <pattern>`, `pytest --cov=fundainsight --cov=fincli` (informational; not enforced this phase). **State explicitly that coverage threshold is deferred to Phase 3 (§8)** and that the repo currently has no tests (Phase 2 will introduce them). |
| `TOOLS_REFERENCE.md` | NEW | `midas/TOOLS_REFERENCE.md` | Section layout: Build/Run, Test, Lint, Format, Type-check, MCP tools, Claude Code hook commands | Build/Run: `pip install -r requirements.txt`, `python -m fincli`, `python -m fundainsight`, `./run.sh` / `run.bat`. Test: `pytest tests/`, `pytest -k <name>`. Lint: `ruff check .`, `ruff check --fix .`. Format: `ruff format .`, `ruff format --check .`. Type-check: `mypy fundainsight/ fincli/ core/ config/`. MCP tool list: same as Midas TOOLS_REFERENCE.md. Hook commands: which hook fires on which event, env var overrides (matching `on-stop.js` envars). |

### 6.2 Section 2 — `.claude/` harness

| File | Action | Midas source path | Retain | Retarget |
|---|---|---|---|---|
| `.claude/settings.json` | NEW | `midas/.claude/settings.json` | Full structure: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, `SessionStart` → `load-rules.js` (10s timeout), `PreToolUse:Read` → `pre-read.js` (10s), `PostToolUse:Edit\|Write` → `post-edit.js` (60s), `Stop` → `on-stop.js` (600s) | Identical. Hook script names and timeouts unchanged. |
| `.claude/settings.local.json` | MERGE | `midas/.claude/settings.local.json` (consult for permission shape) | Existing local permissions in algo_beta | Add Python/git/pytest permissions: `Bash(python:*)`, `Bash(python -m:*)`, `Bash(pytest:*)`, `Bash(ruff:*)`, `Bash(mypy:*)`, `Bash(pip:*)`, `Bash(git:*)`. **OPEN QUESTION 1** — exact final permission list to confirm with user. |
| `.claude/hooks/load-rules.js` | COPY | `midas/.claude/hooks/load-rules.js` | Entire file. The `RULE_FILES` array already points to `agents/rules/_shared-workflow.md`, `agents/rules/preflight.md`, `agents/rules/orchestrator.md` — no path changes needed because we mirror the same `agents/rules/` layout. | None. |
| `.claude/hooks/pre-read.js` | COPY | `midas/.claude/hooks/pre-read.js` | Entire file (read it during implementation; if it contains Go-specific logic, retarget — initial review suggests it's generic) | **OPEN QUESTION 2** — verify no Go references during implementation. If any, replace with Python equivalents. |
| `.claude/hooks/post-edit.js` | RETARGET | `midas/.claude/hooks/post-edit.js` | Full skeleton: secret scan, OWASP scan, lint-fix dispatch, doc-update reminder, `systemMessage` warnings | Replace `runLintFix`'s `gofmt -w` branch with: when `ext === '.py'` → `npx`-equivalent shell calls to `ruff check --fix "${filePath}"`, `ruff format "${filePath}"`, `mypy "${filePath}"`. Drop the Go branch. Keep the secret-scan and OWASP scan blocks unchanged (regexes are language-agnostic). Keep the doc-update reminder (`getDocUpdateNeeded`) and update the patterns in `utils.js` (see below) so it triggers on the right Python files. |
| `.claude/hooks/on-stop.js` | RETARGET | `midas/.claude/hooks/on-stop.js` | Skeleton: `stop_hook_active` infinite-loop guard, session loading, git-diff fallback, per-service quality-gate loop, dependency audit, skill-reminder builder, final `systemMessage` | **Run repo-level checks, not per-service.** Replace the `for (const svc of affectedServices)` loop with a single block that runs: `ruff check .`, `ruff format --check .`, `mypy fundainsight/ fincli/ core/ config/`, `pytest tests/`. **Mypy must be wired through the `warnings` channel, not the `issues` channel** (mypy errors surface in `systemMessage` as advisory text, do not block the Stop event). This is intentional Phase 1 behavior so the user sees the error count without blocking every session. Phase 4 (§8.3) flips this to the issues channel once type hints land. **Coverage check disabled** — keep the `runCoverageCheck` function stub returning `{skipped: true, reason: 'Phase 3 deferred — no coverage threshold yet'}` so Phase 3 only has to flip the knob. Replace `runDependencyAudit`'s `govulncheck` with `pip-audit -r requirements.txt` **if** `pip-audit` is on PATH; if not, return `{success: true, note: 'pip-audit not installed, skipping vulnerability audit'}` (matches Midas graceful skip pattern). Drop TypeScript-specific branches. Keep skill reminders (`/docs-update`, `/github-tracking`). |
| `.claude/hooks/utils.js` | ADAPT | `midas/.claude/hooks/utils.js` | Full skeleton: project-root detection, Git Bash path normalization, session tracking, secret/security/sensitive-file detection, I/O helpers (`readStdin`, `respondOk`, `respondBlock`) | Replace the `SERVICES` map with algo_beta module map: `fincli` → `fincli/`, `fundainsight` → `fundainsight/`, `core` → `core/`, `config` → `config/`, `logger` → `logger/`. `runtime: 'python'`. `testCommand`: `pytest tests/<unit\|domain\|e2e>/<name>` per module **OR** repo-wide `pytest tests/` (decision: **repo-wide for Phase 1**, can refine in Phase 2 once tests exist). `lintCommand`: `ruff check <module>/`. `buildCommand`: `python -c "import <module>"` (smoke import; Python has no separate build step). `testableExtensions`: `['.py']`. Replace `SERVICE_DEPENDENCIES` with: `core` → `[fincli, fundainsight]`, `config` → `[fincli, fundainsight]`, `logger` → `[fincli, fundainsight]`, `fincli` → `[fundainsight]` (fundainsight uses fincli's screener output). Update `NON_TESTABLE_PATHS` to include `workspace_output/`, `workspace_materials/`, `htmlcov/`, `dist/`, `benchmarks/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`. Update `NON_TESTABLE_EXTENSIONS` (already covers `.md`/`.json`/etc.; add `.csv`, `.pstat`). Update `DOC_TRIGGER_PATTERNS`: contracts trigger on `fincli/resource/params/.*\.py$`, `fundainsight/calculators/.*\.py$`, `core/configuration/.*\.py$`; architecture trigger on `fincli/app/main\.py$`, `fundainsight/app/picker\.py$`, `*/__main__\.py$`, `pyproject\.toml$`. Keep secret/sensitive/security regexes as-is. |
| `.claude/hooks/.gitignore` | COPY | `midas/.claude/hooks/.gitignore` | Full file (ignores `.session-edits.json`, `.rules-loaded`) | None. |
| `.claude/agnets/` (typo dir) | DELETE | n/a | n/a | Empty folder; remove. |

### 6.3 Section 3 — `agents/` folder (top-level)

| File | Action | Midas source path | Retain | Retarget |
|---|---|---|---|---|
| `agents/roles/code-architect.md` | ADAPT | `midas/agents/roles/code-architect.md` | Front-matter (`name: ARCH`, description), working-style principles, Clean Architecture pragmatism, ARCH output structure | Replace Go conventions with Python: reference `pyproject.toml`, Pydantic `SystemSettings` base, Singleton `logger`, Click command-group structure. Drop REST/handler/openapi vocabulary. Cite algo_beta files: `core/configuration/configurator.py`, `config/config.py`, `fincli/app/main.py`, `fundainsight/app/picker.py`. |
| `agents/roles/backend-architect.md` | ADAPT | `midas/agents/roles/backend-architect.md` | Front-matter, "domain-logic architect" framing, working-style, definition-of-done | Drop database/REST/auth sections. Refocus on: domain logic in `fundainsight/calculators/` (equity_calc, filters), orchestration in `fundainsight/app/picker.py`, screener pipeline in `fincli/app/main.py`. Reference `ThreadPoolExecutor` enrichment pattern, Pydantic config validation, pandas DataFrame contracts. |
| `agents/roles/frontend-developer.md` | KEEP & ADAPT | `midas/agents/roles/frontend-developer.md` | Front-matter, working-style, definition-of-done | **Per §9 hedge.** Add prominent note in body: "**No current frontend surface in algo_beta.** Invoke this role only when explicitly extending the system with UI (TUI / dashboard / notebook)." Replace web/React vocabulary with: Click command groups, output formatting (colorama colored output, table formatters), terminal UX (typing-effect logger, progress indicators), CSV-to-table presentation. Keep working-style and DoD shape. |
| `agents/roles/ui-designer.md` | KEEP & ADAPT | `midas/agents/roles/ui-designer.md` | Front-matter, working-style, definition-of-done | **Per §9 hedge.** Same prominent caveat: "no current UI surface". Retarget to: CLI ergonomics (option naming, defaults, `--help` text quality), error message clarity (actionable next step), prompt design for interactive Click prompts, color/symbol conventions for `colorama` output. |
| `agents/roles/verifier.md` | ADAPT | `midas/agents/roles/verifier.md` | Verifier output format (Result, Verification Summary, Test Results table, Issues Found table, Next Steps + HANDOFF_TO) | Test-suite list rows: Unit tests (pytest), Domain tests (pytest), E2E tests (pytest with fixture data), Lint (ruff), Format (ruff format --check). **Types (mypy) row: mark "advisory only — Phase 4 promotes to gate"** so VERIFIER reports mypy results without treating them as a fail. **Coverage row: mark "deferred (Phase 3)" until §8 ships.** Add CSV-output schema validation: when CSV-producing code is touched, verifier must run a representative `python -m fincli --dry-run` (if such flag exists) or invoke the picker on fixture data and inspect column names + dtypes. OQ3 — does any `--dry-run` mechanism exist today, or do we need a fixture-only invocation path? Implementation may need to fall back to "manual confirmation". |
| `agents/roles/qa-debugger.md` | ADAPT | `midas/agents/roles/qa-debugger.md` | QA triage output (severity, repro steps, root-cause hypothesis, affected area, evidence) | Severity table unchanged. Affected area enum: BACKEND (any source module) | DATA (CSV / Yahoo / Finviz response) | CONFIG (Pydantic / JSON config) | UI (only if FRONTEND/UX_UI in play) | UNKNOWN. Repro steps must include the exact CLI invocation and any input flags. Evidence must include the offending CSV row(s) when output is wrong. |
| `agents/roles/code-reviewer.md` | ADAPT | `midas/agents/roles/code-reviewer.md` | Reviewer output format, focus areas (readability, maintainability, security, performance) | Replace Go conventions with: PEP 8 via ruff, type hints (`from __future__ import annotations`, `typing` module usage), Pydantic patterns (model validators, `Field` defaults, `model_config`), **Google-style docstrings** (resolved 2026-05-02 — no existing convention; Google is most popular today, future-friendly to ruff `D` rules and Sphinx napoleon). Security focus: cfscrape User-Agent leak, hardcoded API keys, CSV injection risk in `=` / `+` / `-` / `@` prefixed strings, secret patterns from `utils.js` regexes. |
| `agents/roles/project-planning-handoff-specialist.md` | COPY | `midas/agents/roles/project-planning-handoff-specialist.md` | Entire file (language-neutral) | Spot-check for any Go/Midas-specific path references; replace with algo_beta equivalents if found. |
| `agents/rules/_shared-workflow.md` | ADAPT | `midas/agents/rules/_shared-workflow.md` | YAML front-matter (`alwaysApply: true`), MANDATORY-STEPS preamble, MCP-tool list, role table, validation cycle ASCII, response-format spec, VERIFIER/REVIEWER/QA responsibility blocks | Role table includes `FRONTEND` and `UX_UI` rows but with footnote: "**Note:** algo_beta has no current frontend surface. Invoke FRONTEND/UX_UI only when explicitly extending the system with UI (TUI / dashboard / notebook)." Reference rewritten `ARCHITECTURE.md`/`CONTRACTS.md`/`TESTING.md`/`AGENTS.md`. **Update VERIFIER coverage row from "90%" to "deferred (Phase 3)" and the mypy/types row to "advisory — Phase 4 promotes to gate"**, so VERIFIER's documented expectations match the actual `on-stop.js` wiring shipping in Phase 1. MCP tool list unchanged. |
| `agents/rules/preflight.md` | ADAPT | `midas/agents/rules/preflight.md` | Pre-implementation checklist structure | Python checklist items: ran `ruff check`, ran `mypy <touched module>`, identified affected modules in `fincli/`/`fundainsight/`/`core/`/`config/`/`logger/`, located the relevant Click command in `app/cli.py`, located the relevant Pydantic config in `config/config.py`. Drop Go-test / `go vet` items. |
| `agents/rules/orchestrator.md` | ADAPT | `midas/agents/rules/orchestrator.md` | Mode flowcharts (PLAN_AND_CREATE, EXECUTE, REFACTOR, DEBUG), routing logic, ARCH output structure, GitHub-issue creation, validation cycle | Routing decisions must include FRONTEND/UX_UI **with caveat** — these are skipped by default unless the request explicitly mentions UI/TUI/dashboard/notebook output. Otherwise BACKEND covers all "implementation" routes. Reference Python tooling for VERIFIER (pytest/ruff/mypy). |
| `agents/rules/load-context.md` | ADAPT | `midas/agents/rules/load-context.md` | Load-context flow (which docs to read for which task) | Rewrite all file references for algo_beta. Examples: API change → `CONTRACTS.md` (CLI/CSV section); domain-logic change → `ARCHITECTURE.md` + `fundainsight/calculators/`; config change → `config/config.py` + `core/configuration/configurator.py`; new CLI command → `fincli/app/cli.py` or `fundainsight/app/cli.py` + Click conventions in `CLAUDE.md`. |
| `agents/rules/scaffold-module.md` | ADAPT | `midas/agents/rules/scaffold-module.md` | Module scaffolding flow (when adding a new module) | Replace Go package scaffolding with Python: create `<module>/`, `<module>/__init__.py`, `<module>/app/` (cli + main), `<module>/utils/`, `<module>/resource/` (if static data), test scaffolds at `tests/unit/<module>/`, `tests/domain/<module>/`, `tests/e2e/<module>/`. Include Pydantic settings model template. Include Click command-group template. |

### 6.4 Section 4 — `docs/` tree

| Path | Action | Midas source path | Retain | Retarget |
|---|---|---|---|---|
| `docs/THESIS.md` | NEW | `midas/docs/THESIS.md` | Section structure: Vision, Current Phase, Roadmap, Scope Boundaries, Non-Goals | **Drafted from existing `README.md` + `CLAUDE.md` + `ARCHITECTURE.md`.** Vision: identify undervalued stocks via two-stage pipeline (screen → fundamental analysis). Current Phase: MVP CLI, no UI, no tests. Roadmap: Phase 2 (introduce pytest tests), Phase 3 (enable coverage gate), then any of TUI/notebook/cleanup of `equity_calc.adjust_assets` bug, configurability of country/sector exclusions. Scope Boundaries: not a backtest engine, not a portfolio optimizer, not a trading bot. Non-Goals: real-time pricing, broker integration. **User will revise after.** |
| `docs/FEEDBACK-LOG.md` | NEW | `midas/docs/FEEDBACK-LOG.md` | Header, "What goes here" guidance, append-only entry template (`### YYYY-MM-DD — Topic`, "What", "Why", "How to apply") | Empty body (no entries yet). |
| `docs/MODULE_REFERENCE.md` | NEW | `midas/docs/API_DOCUMENTATION.md` | High-level structure: per-module section with purpose, public surface, key files, data shapes, error modes, integration notes | algo_beta has **no API**. Renamed `MODULE_REFERENCE.md` because the document references modules, not endpoints. Section per module: `fincli` (screener pipeline, Finviz query builder, web_scraper, CSV output), `fundainsight` (Yahoo enrichment, equity_calc, filters, CSV output), `core` (configuration framework), `config` (Pydantic settings + history), `logger` (Singleton logger). Each section: purpose, key files, public functions/classes, data shapes (DataFrames, CSV columns, Pydantic models), error modes, integration notes (which other modules depend on it). |
| `docs/bugs/README.md` | NEW | `midas/docs/bugs/` (directory convention, no README in source) | Naming convention `BUG-NNN-slug.md`, recommended template (Symptom, Repro, Root cause, Fix, Regression test, Date) | Identical convention. Mention that `equity_calc.adjust_assets` `not int` bug from CLAUDE.md is a candidate first entry but not auto-created here. |
| `docs/bugs/archive/` | NEW (empty) | `midas/docs/bugs/archive/` | Folder shape | None — empty. |
| `docs/refactoring/README.md` | NEW | `midas/docs/refactoring/` (directory) | Convention: refactoring specs land here, naming `<topic>-spec.md`, archived after completion | Identical convention. Note this very spec lives in `docs/superpowers/specs/` (chronological per-feature) rather than `refactoring/` because it's a one-shot harness replication, not an iterative refactor. |
| `docs/refactoring/archive/` | NEW (empty) | `midas/docs/refactoring/archive/` | Folder shape | None — empty. |
| `docs/reviewer/README.md` | NEW | `midas/docs/reviewer/` (directory; AGENTS.md describes its role) | Convention: review-follow-up trackers per topic, archived once issues close | Identical convention. |
| `docs/reviewer/archive/` | NEW (empty) | `midas/docs/reviewer/archive/` | Folder shape | None. |
| `docs/superpowers/specs/` | NEW (already created for this spec) | `midas/docs/superpowers/specs/` | Convention: chronological per-feature design specs, name `YYYY-MM-DD-<slug>.md` | Identical. |
| `docs/superpowers/plans/` | NEW (empty) | `midas/docs/superpowers/plans/` | Convention: future implementation plans land here | Identical. |
| **SKIP**: `docs.go` | DROP | `midas/docs/docs.go` | n/a | Go swagger generator. algo_beta has no swagger. |
| **SKIP**: `openapi.yaml` | DROP | `midas/docs/openapi.yaml` | n/a | No REST API. |
| **SKIP**: `swagger.json` | DROP | `midas/docs/swagger.json` | n/a | No REST API. |
| **SKIP**: `swagger.yaml` | DROP | `midas/docs/swagger.yaml` | n/a | No REST API. |
| **SKIP**: `postman_collection.json` | DROP | `midas/docs/postman_collection.json` | n/a | No REST API. |
| **SKIP**: `integration/` | DROP | `midas/docs/integration/` | n/a | Midas-specific archive. |
| **SKIP**: `sec_data_cleaning_guide.md` | DROP | `midas/docs/sec_data_cleaning_guide.md` | n/a | Go SEC EDGAR pipeline; no analogue in algo_beta. |
| **SKIP**: `columns name.txt` | DROP | `midas/docs/columns name.txt` | n/a | Already lives at `fincli/resource/` per CLAUDE.md note; would be duplicate. |

### 6.5 Section 5 — Cross-cutting

#### 6.5.1 `pyproject.toml`

**Action:** EDIT (not REWRITE — preserve `[project]` block; replace stale dep, add tooling sections).

| Block | Action | Notes |
|---|---|---|
| `[project]` `dependencies` | EDIT | Replace `yfinance` with `yahooquery`. Deduplicate the doubled `requests` and `urllib3<2` lines. |
| `[project.optional-dependencies]` `dev` | NEW | `ruff>=0.6`, `mypy>=1.10`, `pytest>=8`, `pytest-cov>=5`, `types-beautifulsoup4`. (Coverage tool installed for Phase 3 readiness; not enforced by hooks yet. `types-beautifulsoup4` provides community type stubs so `bs4` does not need a mypy override.) |
| `[tool.ruff]` | NEW | `line-length = 100`. `target-version = "py312"`. `extend-exclude = ["workspace_output", "workspace_materials", "dist", "htmlcov", "wisdom_fruit", "shared", "example", "src", "benchmarks", "__pycache__"]`. |
| `[tool.ruff.lint]` | NEW | `select = ["E", "F", "W", "I", "B", "UP", "N", "SIM"]`. `ignore = []`. (Resolved 2026-05-02 — user picked the conservative rule set. `D` (pydocstyle / Google docstrings) is **not** enabled in Phase 1 to avoid flooding; revisit when type hints + docstrings are in better shape.) |
| `[tool.ruff.format]` | NEW | Default settings (`quote-style = "double"`, `indent-style = "space"`). |
| `[tool.mypy]` | NEW | `python_version = "3.12"`. `files = ["fundainsight", "fincli", "core", "config", "logger"]`. **`strict = true`** from day one (user direction — long-term target is globally strict). The high error count expected on day one is acceptable because **mypy is wired through the `warnings` channel in `on-stop.js` for Phase 1** (advisory, not blocking). Phase 4 (§8.3) flips mypy from warnings to a hard gate once type hints land and the warning count reaches zero. |
| `[[tool.mypy.overrides]]` | NEW | One block: `module = ["cfscrape", "cfscrape.*", "yahooquery", "yahooquery.*"]` with `ignore_missing_imports = true`. These two libraries ship no inline type hints, no `py.typed` marker, and no community stubs on PyPI; without the override mypy would emit `import-untyped` errors for every import. `bs4` does **not** need an override because `types-beautifulsoup4` is in the dev deps. `pandas`, `pydantic`, `click`, `colorama` are already typed and need no override. |
| `[tool.pytest.ini_options]` | NEW | `testpaths = ["tests"]`. `python_files = "test_*.py"`. `python_classes = "Test*"`. `python_functions = "test_*"`. `addopts = "-ra"`. (No `--cov` flag — coverage is informational, not enforced.) |

#### 6.5.2 `.gitignore`

**Action:** EDIT (single targeted append).

Append (idempotent — check first):
```
# Claude Code hook session state
.claude/hooks/.session-edits.json
.claude/hooks/.rules-loaded
.claude/projects/
```

#### 6.5.3 Files explicitly NOT touched

- All source: `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `scripts/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`.
- `requirements.txt` (runtime deps unchanged; dev deps go in pyproject `[project.optional-dependencies]`).
- Existing `tests/` content (`tests/unit/`, `tests/domain/`, `tests/e2e/` and their `__pycache__` remain; no new test files added — that's Phase 2).
- `run.bat`, `run.sh`, `Dockerfile`-equivalent files (none exist; `package.json` / `package-lock.json` are unrelated artifacts left alone).
- `singleton.py` at the repo root (unrelated, untouched).
- `workspace_output/`, `workspace_materials/`, `htmlcov/`, `dist/`, `benchmarks/`, `coverage.xml`, `profile_results.pstat` (build/output artifacts — left alone, ignored by ruff via `extend-exclude`).

---

## 7. Tooling Decisions

### 7.1 Why `ruff` (lint + format)

- Single binary replaces black + isort + flake8 + pyupgrade + pep8-naming. One config block, one PATH entry, one hook command.
- Roughly 10–100× faster than the Python alternatives — fits inside the 60s `post-edit` timeout comfortably even for large saves.
- `ruff format` is an opinionated, black-compatible formatter; it can replace `black` 1:1 without a separate tool.
- `ruff check --fix` auto-fixes mechanical issues (unused imports, formatting drift) inside the post-edit hook, mirroring Midas's `gofmt -w` behavior.

### 7.2 Why `mypy` (type checking) — strict from day one, advisory in Phase 1

- The de facto standard for Python type checking; widely understood by collaborators.
- `pyproject.toml` integration is mature.
- **Config: `strict = true` from day one**, per user direction — the long-term goal is a globally-strict codebase, and starting strict makes the gap visible from the start. The expected hundreds of day-one errors are **acceptable in Phase 1** because the `on-stop.js` hook surfaces mypy through its `warnings` channel (advisory, not blocking). The user sees the error count without blocking work.
- **Why advisory rather than blocking initially:** algo_beta currently has zero type hints. A blocking gate on day one would either force a massive type-hint sprint (out of Phase 1 scope per Goal G9) or create chronic hook failures that train the user to ignore the gate. The warning-channel approach gives the type-rigor signal without the blocking penalty, then Phase 4 (§8.3) flips the switch once the count reaches zero.
- **Override list:** `cfscrape` and `yahooquery` get `ignore_missing_imports = true` because they ship no upstream type info. `bs4` is handled by adding `types-beautifulsoup4` to dev deps (cleaner than overriding). `pandas`, `pydantic`, `click`, `colorama` (modern versions) ship `py.typed` and need no override.
- Alternatives considered:
  - **pyright**: faster, stricter by default, but introduces a Node/TypeScript-adjacent dependency mismatch (the toolchain is otherwise pure Python). Skipped.
  - **pytype**: Google-maintained but Python 3.12 support has historically lagged. Skipped.

### 7.3 Why `pytest` (test runner)

- Existing `tests/{unit,domain,e2e}/` folder structure already implies pytest layout.
- Best-in-class fixture system, parametrize support, and parallel execution via `pytest-xdist` if needed later.
- `pytest-cov` can be added for Phase 3 without changing the test runner.

### 7.4 Why **NO coverage gate** in this phase

- The repo currently has **zero tests** (only `__pycache__` survives in `tests/`). A coverage threshold against zero tests would either trivially pass (if measured against zero lines) or trivially fail (if measured against the whole codebase) — both are useless signals.
- Forcing a coverage gate now would create pressure to write low-quality tests just to satisfy the metric, which is the exact anti-pattern coverage gates are meant to discourage.
- The correct sequence is: **Phase 2** (introduce real, behavior-validating tests for `fundainsight/calculators/` and `core/`), **then Phase 3** (enable coverage threshold once the test suite has substance).

### 7.5 Why `pip-audit` (replacing `govulncheck` in `on-stop.js`)

- Direct dependency-vulnerability counterpart for Python.
- Same graceful-skip pattern as Midas (if not on PATH, returns success with a `note` saying it was skipped).
- Reads `requirements.txt` directly — no extra config needed.

---

## 8. Phased Follow-ups (CRITICAL)

This work is **Phase 1**. Three concrete follow-up phases are deferred. All three must be tracked as named work items so they don't get forgotten.

### 8.1 Phase 2 — Introduce pytest Test Suite

**Trigger:** After this Phase 1 spec ships and the harness is verified working.

**Scope:**
- Create real pytest tests for `fundainsight/calculators/equity_calc.py` (price-to-asset ratio math, `adjust_assets` behavior — and capture the existing `not int` truthy bug as a regression test before/after the fix).
- Create tests for `fundainsight/calculators/filters.py` (country/sector/price filtering correctness on synthetic DataFrames).
- Create tests for `core/configuration/configurator.py` (Pydantic validation success/failure paths).
- Add HTML fixture for `fincli/utils/web_scraper.py` parsing (mock the cfscrape response, assert DataFrame shape).
- Add `yahooquery.Ticker` mock fixtures for `fundainsight/app/picker.py` enrichment.
- **Add type hints incrementally to the modules being tested.** This is the natural moment to drive the mypy warning count down — when you write a test for a function, you also annotate that function's signature. Phase 4 (§8.3) requires the warning count to reach zero before flipping mypy to a hard gate.

**Out of scope for Phase 2:**
- `wisdom_fruit/` (experimental; skip).
- `logger/` (Singleton plumbing; low value, hard to test).
- E2E tests against live Finviz / Yahoo (gated by env var like Midas's `E2E_LIVE=1`).

**Definition of Done for Phase 2:**
- `pytest tests/` passes locally and inside `on-stop.js`.
- At least one test exists per module listed above.
- The `equity_calc.adjust_assets` bug is fixed (the truthy `not int` check) and a regression test pins the corrected behavior.

**Tracking:** Open a follow-up issue / spec at `docs/superpowers/specs/<future-date>-pytest-suite-bootstrap-spec.md` after Phase 1 lands.

### 8.2 Phase 3 — Enable Coverage Gate

**Trigger:** After Phase 2 establishes a meaningful baseline test suite.

**Scope:**
- In `.claude/hooks/on-stop.js`, change `runCoverageCheck` from `{skipped: true, reason: 'Phase 3 deferred'}` to actually invoking `pytest --cov=fundainsight --cov=fincli --cov=core --cov=config --cov-report=term-missing`.
- Parse the coverage summary line; compare against `CONFIG.coverageThreshold` (target: **90%**, matching Midas's threshold per user direction). Lower per-module thresholds may be set during ramp-up if the global 90% is unreachable initially — to be decided when this phase opens.
- Update `TESTING.md` to document the enforced threshold.
- Update `agents/roles/verifier.md` to flip the coverage row from "deferred" to **90%**.
- Update `agents/rules/_shared-workflow.md` VERIFIER block similarly.

**Definition of Done for Phase 3:**
- `on-stop.js` blocks the stop (matching Midas's `issues` pattern, not `warnings`) when coverage drops below 90%.
- `TESTING.md` lists the enforced 90% threshold and the rationale.

**Tracking:** Open a follow-up spec at `docs/superpowers/specs/<future-date>-coverage-gate-enable-spec.md` after Phase 2 lands.

### 8.3 Phase 4 — Promote mypy from Warning to Gate

**Trigger:** When `mypy fundainsight/ fincli/ core/ config/` returns zero errors. This typically follows naturally from Phase 2 (adding tests drives type-hint adoption — see §8.1 scope).

**Scope:**
- In `.claude/hooks/on-stop.js`, move the mypy result from the `warnings` channel to the `issues` channel so it blocks Stop instead of just surfacing advisory text.
- In `.claude/hooks/post-edit.js`, treat mypy errors on the just-edited file as blocking (not advisory) — failure becomes a real local feedback loop.
- Update `agents/roles/verifier.md`: VERIFIER lists mypy as a hard gate, not a "warning under Phase 1".
- Update `agents/rules/_shared-workflow.md` VERIFIER block similarly.
- Update `TESTING.md` with the new policy.
- Decide whether to add ruff `D` rules (Google docstring enforcement) at the same time — natural pairing since the codebase is now in a "fully annotated" state. Track as a sub-decision in the Phase 4 spec.

**Definition of Done for Phase 4:**
- `mypy fundainsight/ fincli/ core/ config/` returns 0 errors against `strict = true` config that has been live since Phase 1.
- `on-stop.js` and `post-edit.js` treat mypy as blocking.
- A new session running `on-stop.js` against a deliberately-mistyped local edit fails the gate.
- `TESTING.md` documents that mypy is now a hard gate.

**Why this is its own phase, not folded into Phase 2:** Type-hint adoption is incremental and may stretch across multiple PRs as different modules get attention. The mypy-as-gate flip is a discrete one-time decision that should happen on its own merit (zero-warning state achieved), not implicitly during a test-introduction PR.

**Tracking:** Open a follow-up spec at `docs/superpowers/specs/<future-date>-mypy-promote-to-gate-spec.md` when the warning count nears zero.

### 8.4 Why these are explicit, not implicit

The user explicitly flagged the risk that "deferred test work" silently disappears. All three phases are documented here so:
- The implementer of Phase 1 doesn't accidentally enable a coverage gate or promote mypy to blocking.
- A future session reading this spec can see the staged plan and where to pick up.
- The `verifier.md` and `_shared-workflow.md` "deferred" / "warnings only" markers are intentional and tied to real next steps, not placeholder oversights.
- Each phase has a concrete trigger condition so it's clear *when* to start it, not just *that* it's pending.

---

## 9. Frontend / UX Role Hedging

### 9.1 Decision

`agents/roles/frontend-developer.md` and `agents/roles/ui-designer.md` are **kept** despite algo_beta currently having no UI surface. The role files are adapted to be Python/CLI-aware (Click command groups, colorama formatting, terminal UX, help-text quality, error-message clarity).

### 9.2 Rationale

- **Hedge for future scope.** Realistic next steps after Phase 2/3 include: a TUI frontend over `fundainsight` filtered output, a Jupyter notebook UI for interactive filter tweaking, a small dashboard exposing the CSV results. Each of those is a "frontend" by any sensible definition.
- **Cheap to keep, expensive to recreate.** The role files are short markdown docs. Removing them and re-creating them in three months when a UI need surfaces is wasted churn.
- **Mirrors Midas exactly.** Keeping the roles preserves the 1:1 mapping between Midas and algo_beta harnesses, so paths in `AGENTS.md` and references in `_shared-workflow.md` work identically.

### 9.3 How the orchestrator treats them

- `agents/rules/orchestrator.md` lists FRONTEND/UX_UI in its routing logic but with an explicit caveat: "**No current frontend surface in algo_beta.** Invoke FRONTEND or UX_UI only when the request explicitly mentions UI, TUI, dashboard, notebook output, or interactive terminal flows. Otherwise, BACKEND covers all implementation work."
- `agents/rules/_shared-workflow.md` includes the same caveat in its role table footnote.
- Each role file (`frontend-developer.md`, `ui-designer.md`) opens with a prominent "**Status: hedge — no current frontend surface**" callout so an agent reading the file knows immediately whether it should be acting on this role.

### 9.4 What changes if/when a UI does ship

- The "no current frontend surface" caveat is removed from `_shared-workflow.md`, `orchestrator.md`, and the two role files.
- The "Status: hedge" header in the role files becomes "Status: active".
- No restructuring of the harness needed — it's already wired.

---

## 10. Files Explicitly Out of Scope

### 10.1 Source code (no changes)

- `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `scripts/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`, `singleton.py`.

### 10.2 Runtime dependency manifest (no changes)

- `requirements.txt` — runtime deps unchanged. (Dev deps live in `pyproject.toml [project.optional-dependencies] dev`.)

### 10.3 Existing tests (no changes)

- `tests/unit/`, `tests/domain/`, `tests/e2e/` and their `__pycache__` content — preserved as-is. Phase 2 adds new test files; this work touches none of them.

### 10.4 Midas docs we DROP (no algo_beta analogue)

- `docs/docs.go` — Go swagger generator.
- `docs/openapi.yaml`, `docs/swagger.json`, `docs/swagger.yaml`, `docs/postman_collection.json` — REST API contracts. algo_beta is a CLI.
- `docs/integration/` — Midas-specific integration archive.
- `docs/sec_data_cleaning_guide.md` — Go SEC EDGAR pipeline guide.
- `docs/columns name.txt` — already lives at `fincli/resource/` per CLAUDE.md.

### 10.5 Build / output artifacts (no changes)

- `workspace_output/`, `workspace_materials/`, `htmlcov/`, `dist/`, `benchmarks/`, `coverage.xml`, `profile_results.pstat`, `package.json`, `package-lock.json`.

---

## 11. Validation Plan

How we'll know the harness works end-to-end after Phase 1 ships:

| # | Validation step | Pass criterion |
|---|---|---|
| V1 | Open a new Claude Code session in `algo_beta`. | `SessionStart` hook fires; `_shared-workflow.md`, `preflight.md`, `orchestrator.md` content appears in context under the header `# Loaded Workflow Rules (agents/rules/)`. |
| V2 | Save any `.py` file in `fundainsight/calculators/`. | `PostToolUse:Edit\|Write` hook fires; `ruff check --fix` and `ruff format` execute against that file (no error if file is already clean); `mypy <file>` runs. |
| V3 | Save a file matching the doc-update trigger patterns (e.g., `fincli/resource/params/<name>.py` or `fundainsight/calculators/filters.py`). | `post-edit.js` `systemMessage` surfaces "Consider updating: CONTRACTS.md" or "ARCHITECTURE.md". |
| V4 | Save a file containing a hardcoded API-key-like string. | `post-edit.js` surfaces a SECRETS WARNING in `systemMessage`. |
| V5 | Trigger a `Stop` event after at least one `.py` edit in the session. | `on-stop.js` runs `ruff check .`, `ruff format --check .`, `mypy fundainsight/ fincli/ core/ config/`, `pytest tests/`. Coverage step is reported as `skipped: true, reason: 'Phase 3 deferred'`. **Mypy errors appear in the `warnings` block of `systemMessage`, NOT the `issues` block** — Stop is not blocked by mypy in Phase 1. Final `systemMessage` lists which gates passed/failed. |
| V6 | Spawn a sub-agent with `subagent_type: ARCH` (or referencing `agents/roles/code-architect.md`). | The sub-agent receives the role file and operates with Python/algo_beta context, not Go/Midas vocabulary. |
| V7 | Read `AGENTS.md`. | Every Tier 1–4 file path resolves to an actual file in the repo (no dangling references). |
| V8 | Read `agents/rules/_shared-workflow.md`. | Role table includes FRONTEND/UX_UI rows with the "no current frontend surface" footnote. References to ARCHITECTURE/CONTRACTS/TESTING/AGENTS resolve. |
| V9 | Run `ruff check .` from the repo root. | Exits 0 (after one auto-fix pass), or surfaces only known/intentional findings (which the user accepts as the Phase 1 baseline — these become Phase 2 input). |
| V10 | Run `mypy fundainsight/ fincli/ core/ config/` from the repo root. | Exits non-zero with **many errors expected** (because `strict = true` against a codebase with zero type hints). The `[[tool.mypy.overrides]]` block silences `cfscrape`/`yahooquery` `import-untyped` errors specifically. Errors that DO surface are the Phase 2/4 baseline — they are advisory in Phase 1 (`on-stop.js` shows them as warnings, not blocking). Verify the error volume looks proportional (hundreds, not tens of thousands — if it's the latter, the override block is wrong). |
| V11 | `python -c "import fincli; import fundainsight"`. | Imports succeed (smoke test that nothing in the harness work broke source code). |
| V12 | `git status` after the change. | No source-code files changed. Only `.claude/`, `agents/`, `docs/`, the seven top-level docs, `pyproject.toml`, `.gitignore`. |

---

## 12. Open Questions

| # | Question | Status | Resolution / Default |
|---|---|---|---|
| OQ1 | Exact final permission list for `.claude/settings.local.json` (which Bash patterns to allowlist for Python/git/pytest)? | OPEN — non-blocking | Use the conservative list from §6.2: `Bash(python:*)`, `Bash(python -m:*)`, `Bash(pytest:*)`, `Bash(ruff:*)`, `Bash(mypy:*)`, `Bash(pip:*)`, `Bash(git:*)`. Tighten after first usage pass via `/fewer-permission-prompts` skill. |
| OQ2 | Does Midas's `pre-read.js` contain any Go-specific logic that needs retargeting? | OPEN — discoverable during implementation | Treat as COPY pending review during implementation; flag any Go references for retarget when found. |
| OQ3 | Does `algo_beta` have a `--dry-run` mechanism today, or do we need a fixture-only invocation path for VERIFIER's CSV-schema validation? | OPEN — non-blocking | Assume no `--dry-run`; document VERIFIER's CSV schema check as "manual confirmation against synthetic fixture data" in Phase 1, automate in Phase 2. |
| OQ4 | Docstring style preference (Google vs NumPy vs reST)? | **RESOLVED 2026-05-02** | **Google style.** No existing convention to preserve (10 files have docstrings but none use a structured format). Google is the most popular Python docstring style today; well-supported by Sphinx (napoleon) and ruff `D` rules (deferred to Phase 4). |
| OQ5 | Exact ruff rule set for `[tool.ruff.lint] select`? | **RESOLVED 2026-05-02** | **Conservative set** (user direction): `["E", "F", "W", "I", "B", "UP", "N", "SIM"]`. `D` rules deferred to Phase 4. |
| OQ6 | Phase 3 coverage threshold? | **RESOLVED 2026-05-02** | **90%** (user direction — match Midas's threshold). Per-module easing during ramp-up may be considered when the Phase 3 spec opens, but the target ceiling is 90%. |
| OQ7 | mypy strict-mode scope (added 2026-05-02)? | **RESOLVED 2026-05-02** | **`strict = true` globally from day one**, but mypy is wired through the `warnings` channel in `on-stop.js` (advisory, not blocking) for Phase 1. Phase 4 (§8.3) flips it to a hard gate once the error count reaches zero. User picked this path because the long-term goal is globally-strict; advisory-then-blocking creates a visible declining error count rather than letting type-rigor drift indefinitely. |
| OQ8 | mypy override list (added 2026-05-02)? | **RESOLVED 2026-05-02** | One block: `module = ["cfscrape", "cfscrape.*", "yahooquery", "yahooquery.*"]` with `ignore_missing_imports = true`. `bs4` covered by `types-beautifulsoup4` in dev deps. `pandas`, `pydantic`, `click`, `colorama` (modern) ship `py.typed`. |

---

## 13. References

### Midas source paths to consult during implementation

- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\AGENTS.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\ARCHITECTURE.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\CLAUDE.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\CONTRACTS.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\README.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\TESTING.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\TOOLS_REFERENCE.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\.claude\settings.json`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\.claude\hooks\load-rules.js`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\.claude\hooks\pre-read.js`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\.claude\hooks\post-edit.js`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\.claude\hooks\on-stop.js`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\.claude\hooks\utils.js`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\agents\roles\` (all eight role files)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\agents\rules\` (all five rule files)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\docs\THESIS.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\docs\FEEDBACK-LOG.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\docs\API_DOCUMENTATION.md`

### Spec-style references

- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\docs\refactoring\valuation-engine-upgrade-spec.md`
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\midas\docs\refactoring\observability-narrative-and-artifacts-spec.md`

### algo_beta paths populated by this work

- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\AGENTS.md` (NEW)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\TOOLS_REFERENCE.md` (NEW)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\ARCHITECTURE.md` (REWRITE)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\CLAUDE.md` (REWRITE)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\CONTRACTS.md` (REWRITE)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\README.md` (REWRITE)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\TESTING.md` (REWRITE)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\.claude\settings.json` (NEW)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\.claude\settings.local.json` (MERGE)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\.claude\hooks\` (NEW — 5 scripts + .gitignore)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\agents\` (NEW — roles/ + rules/)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\docs\` (NEW tree)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\pyproject.toml` (EDIT)
- `C:\Users\Yonatan Levin\Documents\Programming\Projects\FinTech\Strade\algo_beta\.gitignore` (EDIT)

---

## 14. Acceptance Criteria

When implementation is complete, all of the following must be true:

| # | Criterion | Verifier |
|---|---|---|
| AC1 | All seven top-level docs exist and are written in Midas style, retargeted to Python/CLI. | Manual review + V7. |
| AC2 | `agents/` exists at repo root with eight role files and five rule files. | `ls algo_beta/agents/roles/` returns 8 files; `ls algo_beta/agents/rules/` returns 5 files. |
| AC3 | `.claude/agnets/` (typo dir) is deleted. | `test ! -e .claude/agnets`. |
| AC4 | `.claude/settings.json` wires all four hooks at the expected timeouts. | V1, V2, V5. |
| AC5 | `.claude/hooks/{load-rules,pre-read,post-edit,on-stop,utils}.js` plus `.gitignore` exist. | `ls .claude/hooks/` shows 6 files. |
| AC6 | `post-edit.js` runs ruff + mypy (not gofmt) on `.py` saves. | V2. |
| AC7 | `on-stop.js` runs ruff + mypy + pytest at repo level; coverage step is explicitly skipped with reason `'Phase 3 deferred'`; mypy result is wired through the `warnings` channel, NOT the `issues` channel (Phase 4 flips this). | V5. |
| AC8 | `docs/` tree exists with THESIS.md, FEEDBACK-LOG.md, MODULE_REFERENCE.md, bugs/, refactoring/, reviewer/, superpowers/specs/, superpowers/plans/. | `ls -la docs/` matches expected tree. |
| AC9 | `pyproject.toml` has `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.ruff.format]`, `[tool.mypy]` (with `strict = true`), `[[tool.mypy.overrides]]` (covering `cfscrape` and `yahooquery`), `[tool.pytest.ini_options]`, and a `[project.optional-dependencies] dev` group containing `types-beautifulsoup4`. | `grep -c '\[tool.' pyproject.toml >= 5`; `grep 'strict = true' pyproject.toml`; `grep 'types-beautifulsoup4' pyproject.toml`. |
| AC10 | `pyproject.toml` runtime deps no longer reference `yfinance`; `yahooquery` is listed instead. | `grep yfinance pyproject.toml` empty; `grep yahooquery pyproject.toml` non-empty. |
| AC11 | `.gitignore` excludes `.claude/hooks/.session-edits.json`, `.claude/hooks/.rules-loaded`, `.claude/projects/`. | `grep` returns hits. |
| AC12 | No source-code files changed (V12). | `git diff --name-only HEAD~1..HEAD` shows no entries under `fincli/`, `fundainsight/`, `core/`, `config/`, `logger/`, `scripts/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`. |
| AC13 | No changes to `requirements.txt`. | `git diff requirements.txt` empty. |
| AC14 | No new files under `tests/` (Phase 2 work). | `git status tests/` shows only existing `__pycache__` content. |
| AC15 | `agents/rules/_shared-workflow.md` and `agents/rules/orchestrator.md` mention FRONTEND/UX_UI with the "no current frontend surface" caveat. | `grep -i 'no current frontend surface' agents/rules/*.md` matches both files. |
| AC16 | `agents/roles/frontend-developer.md` and `agents/roles/ui-designer.md` open with a "Status: hedge" callout. | Manual review. |
| AC17 | Phase 2, Phase 3, and Phase 4 follow-ups are explicitly named in this spec (§8) and referenced from `TESTING.md` and `agents/roles/verifier.md`. | `grep -i 'phase 2' TESTING.md`, `grep -i 'phase 3' TESTING.md`, and `grep -i 'phase 4' TESTING.md` all match. |
| AC18 | A new Claude Code session loads the three foundation rules into context (V1). | V1. |
| AC19 | Smoke test: `python -c "import fincli; import fundainsight"` succeeds. | V11. |

---

## 15. Next Steps

1. **HUMAN review of this spec.** OQ4, OQ5, OQ6, OQ7, OQ8 are resolved (see §12). OQ1, OQ2, OQ3 remain open but non-blocking — they have safe defaults.
2. After approval, invoke `/superpowers:writing-plans` (or the EXECUTE workflow) to produce the implementation plan from this spec.
3. The implementer executes the plan as a single PR following §6's file-by-file table.
4. Post-merge, run §11's V1–V12 validation against a fresh session.
5. Open Phase 2 spec in `docs/superpowers/specs/<future-date>-pytest-suite-bootstrap-spec.md` once a real test target is identified.
6. Watch the mypy warning count surfaced by `on-stop.js`. When it nears zero, open the Phase 4 spec to flip mypy to a hard gate.

---

## Change Log

| Date | Change |
|---|---|
| 2026-05-02 | Initial DRAFT. Mirrors approved scope from brainstorming session: single-PR retargeted full mirror; ruff + mypy + pytest; coverage gate deferred to Phase 3; FRONTEND/UX_UI roles kept as future-UI hedge with explicit caveats; zero source-code changes. |
| 2026-05-02 (rev 0.2) | Resolved open questions per user direction: **OQ4** Google docstring style (no existing convention to preserve, most popular today); **OQ5** conservative ruff rule set `["E","F","W","I","B","UP","N","SIM"]`; **OQ6** Phase 3 coverage threshold raised from 70% → 90% (match Midas); **OQ7** mypy `strict = true` from day one but wired through `on-stop.js` `warnings` channel (advisory) for Phase 1; **OQ8** mypy override list scoped to `cfscrape` + `yahooquery` only, with `types-beautifulsoup4` added to dev deps for `bs4`. Added **Phase 4** (§8.3) — promote mypy from warning to gate once error count reaches zero. Updated §6.2 (on-stop), §6.3 (code-reviewer), §6.5.1 (pyproject), §7.2 (mypy rationale), §11 (V5/V10), §14 (AC7/AC9/AC17), §15 (next steps). |
