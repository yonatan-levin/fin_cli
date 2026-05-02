# THESIS.md — Product Direction

This file is the **single source of truth for where Fin CLI is going**. All agents (human and AI) should read this before making decisions about scope, architecture, or priorities.

Update this file when: a phase completes, scope changes, or roadmap priorities shift.

---

## Vision

**Fin CLI** surfaces undervalued stocks through a two-stage pipeline: screen then filter.

Stage one (`fincli`) queries Finviz.com's screener API with user-selected fundamental, descriptive, and technical filters. The output is a DataFrame of candidate tickers — typically hundreds — ranked by whatever Finviz criteria the user chose.

Stage two (`fundainsight`) enriches each candidate with Yahoo Finance balance-sheet data, computes price-to-total-assets and price-to-current-assets ratios, applies country/sector/price filters, and writes the result. The intent is to surface stocks trading below their adjusted book value of current assets — a classic net-net screening approach.

The tool operates entirely from the command line. There is no server, no database, no web UI. Outputs land as timestamped CSVs in `workspace_output/` for manual review.

---

## Primary User

**Yonatan Levin** — personal investor making stock-selection decisions across:

- US growth equities
- US value equities
- International companies and ADRs
- Emerging-market tickers where data quality is uneven

Quality bar: personal use, but results must be trustworthy. A bad ratio from a data fetch error is worse than no result; silent corruption is the worst failure mode.

---

## Current Phase

**MVP CLI working. Agent harness in flight (Phase 1). Zero tests.**

The two operating modes (`fincli`, `fundainsight`) are functional and have been used in production for real investment research. The harness rollout (Phase 1) is scaffolding tooling, documentation, and agent-workflow infrastructure to make the codebase safe for AI-assisted development.

Test bodies do not yet exist. The folder structure (`tests/unit/`, `tests/domain/`, `tests/e2e/`) is in place.

---

## Roadmap

### Phase 1 — Agent harness + tooling (current)

Tracked in `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.

- Bootstrap Python tooling: `ruff` (lint/format), `mypy strict` (advisory), `pytest` config, `pip-audit` hook.
- Rewrite top-level docs: `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, plus new `TOOLS_REFERENCE.md` and `AGENTS.md`.
- Scaffold `agents/` directory: shared workflow rules + per-role context files (ARCH, BACKEND, VERIFIER, REVIEWER, QA).
- Scaffold `docs/` tree: this file, `FEEDBACK-LOG.md`, `MODULE_REFERENCE.md`, bug/refactoring/reviewer subfolders.
- Install Claude Code hooks: `SessionStart` (load-rules), `PostToolUse:Edit|Write` (per-edit lint + mypy + secret scan), `Stop` (repo-wide ruff + mypy + pytest).
- `mypy strict` runs in **advisory** mode throughout Phase 1 — errors are visible but do not block commits. The codebase has almost no type hints today; the count is expected to be high.

**Completion trigger:** `AGENTS.md` merged to `master` with all hooks green.

### Phase 2 — Test suite for calculators and core

- Introduce real `pytest` tests for `fundainsight/calculators/` (equity_calc, filters) and `core/configuration/` (config_base, configurator, json converter).
- Add HTML fixture and `yahooquery` mock for the screener pipeline end-to-end test.
- Add type hints incrementally to modules being tested — driving the mypy advisory count down.
- Fix the `equity_calc.adjust_assets` `not int` truthy-check bug as part of writing its regression test (the bug causes the second branch to always execute; the fix changes the condition, and the test pins the corrected behavior).
- Fix the `build_config` hard-coded history path bug: `core/configuration/configurator.py` derives the `filter_history.json` location from `os.path.realpath('fundainsight')` regardless of caller. `fincli --history` therefore reads/writes to the wrong location.

**Completion trigger:** `pytest tests/` green with meaningful coverage across calculators and core.

### Phase 3 — Coverage gate at 90%

- Enable the coverage gate in `.claude/hooks/on-stop.js` at **90%**.
- Update `TESTING.md`, `agents/roles/verifier.md`, and `agents/rules/_shared-workflow.md` to document the enforced threshold.
- Coverage gate applies to `fundainsight/calculators/`, `core/`, and `config/` at minimum.

**Completion trigger:** `pytest --cov` reports >= 90% on the gated modules; `on-stop.js` fails the session on regression.

### Phase 4 — mypy hard gate

- Promote mypy from the `warnings` channel to the `issues` channel in `on-stop.js` (blocking) and from advisory to blocking in `post-edit.js`.
- Trigger: `mypy fundainsight fincli core config` reports zero errors.
- Optionally enable ruff `D` rules (Google docstring enforcement) at the same time.

**Completion trigger:** Zero mypy strict errors across the four main packages; hook wiring updated.

### Beyond Phase 4

- **Make hardcoded filters configurable.** `picker.py` hard-codes the excluded countries (`Brazil, Chile, India, Bermuda, China`) and the excluded sector (`Energy`), plus the ratio threshold (`1`). These should move into `Config` so they are user-overridable per run without editing source.
- **TUI / dashboard / notebook frontend.** The current UX is a series of CLI prompts. A richer interface — a `textual` TUI, a Jupyter notebook wrapper, or a lightweight web dashboard — would reduce friction for exploratory screening sessions.
- **Additional ratio models.** The current model computes two ratios (price-to-assets, price-to-current-assets). Adding enterprise-value-to-EBITDA, price-to-earnings, or price-to-free-cash-flow columns would broaden the filter surface.

---

## Scope Boundaries

Fin CLI is **a screening and filtering tool**. It answers: "which tickers are trading below their adjusted book value of current assets, given these Finviz criteria?"

It is **not**:

- A backtest engine — it does not simulate trading against historical prices.
- A portfolio optimizer — it does not allocate weights, compute correlation, or minimize variance.
- A trading bot — it does not place orders or connect to any broker API.

---

## Non-Goals

- **Real-time pricing.** The tool uses 30-day average price from Yahoo Finance. Intraday prices are out of scope.
- **Broker integration.** No OAuth flows, no order entry, no position tracking.
- **Paper trading.** No simulation of fills, slippage, or portfolio P&L.
- **Stochastic simulation.** No Monte Carlo. No scenario distributions. Ratios are point-in-time.
- **PyPI distribution.** Source-only for personal use; packaging for public distribution is out of scope.

---

## Design Principles

1. **Calculation correctness over engineering elegance.** When a financial ratio is wrong, the user makes a bad investment decision. Correctness is the non-negotiable constraint; clean code is the secondary goal.

2. **Data sources are messy and partial — graceful degradation always.** Yahoo Finance frequently returns `None`, missing fields, or mismatched time periods. The pipeline must handle these gracefully: log a warning, drop the row, continue. Silent corruption (wrong number propagated as correct) is the worst outcome.

3. **Configuration over hardcoding.** Every filter threshold, country exclusion, or sector exclusion that a user might want to adjust should live in `Config`, not as a literal in a function body. The current hardcoded filters in `picker.py` are tech debt, not intentional design.

4. **Singleton logger everywhere.** `from logger import logger` is the only valid way to log. No `print` statements in non-CLI paths. No second logger instances. The typing-effect console handler, file handler, and JSON handler are all governed by the Singleton.

5. **Parallel enrichment, synchronous everything else.** The Yahoo Finance enrichment loop in `fundainsight` uses `ThreadPoolExecutor` because it is I/O-bound fan-out. Everything else (screener pipeline, config loading, filter chain) is synchronous and easier to reason about that way.

---

## Infrastructure Constraints

- **Local-only project** — no remote issue tracker. Work is tracked in `docs/reviewer/`, `docs/bugs/`, and session notes.
- **Windows dev environment** — Yonatan works on Windows 11. Path separators, batch launchers (`run.bat`), and WSL-awareness matter.
- **Finviz rate limits** — `cfscrape` handles Cloudflare but the screener still rate-limits. `fetch_page_sync` uses exponential backoff; do not remove it.
- **Yahoo Finance reliability** — `yahooquery` has no SLA. Missing balance-sheet quarters are common for small-cap and international tickers. The pipeline drops rather than imputes.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-02 | Initial file. Drafted from `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, and the agent-harness spec. |
