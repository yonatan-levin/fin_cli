# THESIS.md — Product Direction

This file is the **single source of truth for where Fin CLI is going**. All agents (human and AI) should read this before making decisions about scope, architecture, or priorities.

Update this file when: a phase completes, scope changes, or roadmap priorities shift.

---

## Vision

**Fin CLI** is a personal-use command-line stock screener built on top of Finviz.com.

The user picks fundamental, descriptive, and technical filter values; the tool builds the corresponding Finviz screener URL, scrapes every paginated result page through `cfscrape` (Cloudflare bypass), parses the HTML stock table with BeautifulSoup, and writes a timestamped CSV to `workspace_output/`. The CSV is a working surface for manual review — open it in Excel and follow the `=HYPERLINK(...)` cells back to Finviz quote pages, or load it into pandas for further filtering.

The tool operates entirely from the command line. There is no server, no database, no web UI.

---

## Primary User

**Yonatan Levin** — personal investor making stock-selection decisions across:

- US growth equities
- US value equities
- International companies and ADRs
- Emerging-market tickers where data quality is uneven

Quality bar: personal use, but results must be trustworthy. A row that silently fails to parse and disappears from the output is worse than an obvious error; silent corruption is the worst failure mode.

---

## Current Phase

**MVP CLI working. Agent harness in flight (Phase 1). Single-mode reduction landed (2026-05-04). Zero tests.**

The screener (`python -m fincli`) is functional and has been used in production for real investment research. The harness rollout (Phase 1) is scaffolding tooling, documentation, and agent-workflow infrastructure to make the codebase safe for AI-assisted development.

The single-mode reduction (`docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`) removed the previously-bundled `fundainsight/` fundamental-analysis package and several abandoned scaffolds, retargeting the project to a single CLI: the Finviz screener. Two follow-up specs (`docs/refactoring/cli-entry-point-spec.md`, `docs/refactoring/history-path-config-spec.md`) capture deferred work.

Test bodies do not yet exist. The folder structure (`tests/unit/`, `tests/domain/`, `tests/e2e/`) is in place.

---

## Roadmap

### Phase 1 — Agent harness + tooling (current)

Tracked in `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.

- Bootstrap Python tooling: `ruff` (lint/format), `mypy strict` (advisory), `pytest` config, `pip-audit` hook.
- Rewrite top-level docs: `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `README.md`, `TESTING.md`, plus new `TOOLS_REFERENCE.md` and `AGENTS.md`.
- Scaffold `agents/` directory: shared workflow rules + per-role context files.
- Scaffold `docs/` tree: this file, `FEEDBACK-LOG.md`, `MODULE_REFERENCE.md`, bug/refactoring/reviewer subfolders.
- Install Claude Code hooks: `SessionStart` (load-rules), `PostToolUse:Edit|Write` (per-edit lint + mypy + secret scan), `Stop` (repo-wide ruff + mypy + pytest).
- `mypy strict` runs in **advisory** mode throughout Phase 1 — errors are visible but do not block commits. The codebase has almost no type hints today; the count is expected to be high.

**Completion trigger:** `AGENTS.md` merged to `master` with all hooks green.

### Phase 2 — Test suite for the screener pipeline

- Introduce real `pytest` tests for `fincli/stock_screening/` (the BeautifulSoup parser), `fincli/utils/quary_builders.py` (URL construction), `fincli/app/main.py` (`convert_market_cap_to_numeric`, the screener orchestrator), and `core/configuration/` (config_base, configurator, json converter).
- Add an HTML fixture for the screener parser end-to-end test.
- Add type hints incrementally to modules being tested — driving the mypy advisory count down.
- Move the hard-coded history path string out of `core/configuration/configurator.py` into a `Config` field — design tracked at `docs/refactoring/history-path-config-spec.md`.

**Completion trigger:** `pytest tests/` green with meaningful coverage across the screener pipeline and core.

### Phase 3 — Coverage gate at 90%

- Enable the coverage gate in `.claude/hooks/on-stop.js` at **90%**.
- Update `TESTING.md`, `agents/roles/verifier.md`, and `agents/rules/_shared-workflow.md` to document the enforced threshold.
- Coverage gate applies to `fincli/`, `core/`, and `config/` at minimum.

**Completion trigger:** `pytest --cov` reports >= 90% on the gated modules; `on-stop.js` fails the session on regression.

### Phase 4 — mypy hard gate

- Promote mypy from the `warnings` channel to the `issues` channel in `on-stop.js` (blocking) and from advisory to blocking in `post-edit.js`.
- Trigger: `mypy fincli core config logger` reports zero errors.
- Optionally enable ruff `D` rules (Google docstring enforcement) at the same time.

**Completion trigger:** Zero mypy strict errors across the four packages; hook wiring updated.

### Beyond Phase 4

- **Add a `[project.scripts]` entry point** so `pip install -e .` exposes a bare `fincli` shell command instead of requiring `python -m fincli`. Design tracked at `docs/refactoring/cli-entry-point-spec.md`.
- **TUI / dashboard / notebook frontend.** The current UX is a series of CLI prompts. A richer interface — a `textual` TUI, a Jupyter notebook wrapper, or a lightweight web dashboard — would reduce friction for exploratory screening sessions.
- **Async I/O for screener fetch.** The pipeline is synchronous to cooperate with Finviz's anti-bot pacing. If profiling shows the page-by-page latency dominates a typical run and Cloudflare tolerates parallel requests, an `httpx`/`aiohttp` rewrite of `fetch_page_sync` is a possibility.

---

## Historical scope (no longer in this codebase)

A previous version of fin_cli bundled a second mode — `fundainsight` — that ran the screener, then enriched each ticker with Yahoo Finance balance-sheet data via `yahooquery` and computed price-to-asset / price-to-current-asset ratios. That mode was removed on 2026-05-04 (see `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`). The git history retains it; anyone who wants to revive the analysis pipeline should fork from the pre-refactor SHA.

---

## Scope Boundaries

Fin CLI is **a screening tool**. It answers: "which tickers does Finviz return for this filter set, and what does the result table look like?"

It is **not**:

- A backtest engine — it does not simulate trading against historical prices.
- A portfolio optimizer — it does not allocate weights, compute correlation, or minimize variance.
- A trading bot — it does not place orders or connect to any broker API.
- A fundamental-analysis pipeline — that mode lived under `fundainsight/` historically and has been removed (see "Historical scope" above).

---

## Non-Goals

- **Real-time pricing.** The Finviz table reflects whatever Finviz's screener view shows; intraday tick-level data is out of scope.
- **Broker integration.** No OAuth flows, no order entry, no position tracking.
- **Paper trading.** No simulation of fills, slippage, or portfolio P&L.
- **Stochastic simulation.** No Monte Carlo. No scenario distributions.
- **PyPI distribution.** Source-only for personal use; packaging for public distribution is out of scope.

---

## Design Principles

1. **Calculation correctness over engineering elegance.** When a market-cap conversion or filter encoding is wrong, the user makes a bad investment decision off the resulting CSV. Correctness is the non-negotiable constraint; clean code is the secondary goal.

2. **Data sources are messy and partial — graceful degradation always.** Finviz HTML can change without notice and individual rows may parse incompletely. The pipeline must handle these gracefully: log a warning, drop the row, continue. Silent corruption (wrong number propagated as correct) is the worst outcome.

3. **Configuration over hardcoding.** Every filter threshold, country exclusion, or sector exclusion that a user might want to adjust should live in `Config`, not as a literal in a function body.

4. **Singleton logger everywhere.** `from logger import logger` is the only valid way to log. No `print` statements in non-CLI paths. No second logger instances. The typing-effect console handler, file handler, and JSON handler are all governed by the Singleton.

5. **Synchronous everywhere.** The screener is intentionally serial so it cooperates with Finviz's anti-bot pacing. Adding fan-out is a deliberate decision, not a default.

---

## Infrastructure Constraints

- **Local-only project** — no remote issue tracker. Work is tracked in `docs/reviewer/`, `docs/bugs/`, `docs/refactoring/`, and session notes.
- **Windows dev environment** — Yonatan works on Windows 11. Path separators, batch launchers (`run.bat`), and WSL-awareness matter.
- **Finviz rate limits** — `cfscrape` handles Cloudflare but the screener still rate-limits. `fetch_page_sync` uses exponential backoff; do not remove it.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-04 | Single-mode reduction. Removed `fundainsight/` and abandoned scaffolds; retargeted Phase 2 scope to the screener pipeline only. Roadmap "Beyond Phase 4" updated to drop fundamental-analysis aspirations and add the CLI entry-point and Config-driven history follow-ups (`docs/refactoring/`). See `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`. |
| 2026-05-02 | Initial file. Drafted from `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, and the agent-harness spec. |
