# THESIS.md — Product Direction

This file is the **single source of truth for where Fin CLI is going**. All agents (human and AI) should read this before making decisions about scope, architecture, or priorities.

Update this file when: a phase completes, scope changes, or roadmap priorities shift.

---

## Vision

**Fin CLI + API** is a personal-use Finviz.com stock screener exposed through two co-equal entry points that share one orchestrator and one filter inventory.

The **CLI** (`fincli/`) is the human-facing surface: the user picks fundamental, descriptive, and technical filter values interactively (or supplies them via `--filter`/`--filters-json`/`--filters-file` in pipeline mode); the tool builds the corresponding Finviz screener URL, scrapes every paginated result page through `cfscrape` (Cloudflare bypass), parses the HTML stock table with BeautifulSoup, and writes a timestamped CSV to `workspace_output/` (or streams to stdout). The CSV is a working surface for manual review — open it in Excel and follow the `=HYPERLINK(...)` cells back to Finviz quote pages, or load it into pandas for further filtering.

The **HTTP API** (`fincli_api/`) is the polyglot / programmatic surface: a FastAPI app exposing `POST /screens` (run a screen, get rows as JSON) and `GET /filters` (the same filter inventory `--list-filters --json` emits). Go, TypeScript, Rust, and other downstream consumers can hit it without a Python runtime, generating typed clients from the committed OpenAPI 3.1.0 snapshot at `docs/api/openapi.{yaml,json}`.

Both entry points delegate to the same orchestrator (`fincli.app.main.screen_to_dataframe`) and the same validator (`fincli.resource.params.validators.list_valid_filters_with_labels`), so the screening behaviour, filter vocabulary, exit-code/HTTP-status classification, and test pyramid are shared. The CLI/API split is a transport concern, not a business-logic fork.

There is no database and no web UI. The HTTP API is a thin transport over the existing CLI orchestrator and is intended to run locally or as a small internal service, not as a public hosted product.

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

**The CLI and HTTP API are operational, and the agent-harness rollout is
complete through its quality-gate phases.**

The screener supports interactive and structured pipeline use, and the HTTP API
exposes the same orchestrator and filter inventory over typed JSON. The default
test suite covers unit, integration, and opt-in live boundaries. The harness now
blocks completion on Ruff, strict mypy across both entry points, the default
pytest suite, and at least 90% aggregate runtime coverage.

Detailed shipped-stream history is indexed in `docs/CHANGELOG.md`.

---

## Roadmap

| Phase | Status | Outcome |
|---|---|---|
| Phase 1 — harness and tooling | **COMPLETE** | Documentation spine, roles/rules, hooks, Ruff, strict-mypy configuration, and pytest tooling installed. |
| Phase 2 — behavior test suite | **COMPLETE** | Unit/integration/API suites and recorded Finviz fixtures cover both entry points. |
| Phase 3 — coverage gate | **COMPLETE** | Stop hook enforces at least 90% aggregate coverage across the shipped runtime surface. |
| Phase 4 — strict-mypy gate | **COMPLETE** | Strict mypy is zero-error and blocking for `fincli`, `fincli_api`, `core`, `config`, `logger`, and `singleton.py`. |
| Phase 5 — HTTP API | **COMPLETE** | FastAPI surface and committed OpenAPI 3.1.0 contract share the CLI orchestrator. |

The governing closeout for Phases 3–4 is
`docs/refactoring/spec/harness-quality-gates-burndown-spec.md`. Ruff
pydocstyle (`D`) enforcement was explicitly not folded into Phase 4; it would
require its own scoped decision.

### Beyond Phase 4

- **TUI / dashboard / notebook frontend.** The current UX is a series of CLI prompts. A richer interface — a `textual` TUI, a Jupyter notebook wrapper, or a lightweight web dashboard — would reduce friction for exploratory screening sessions.
- **Async I/O for screener fetch.** The pipeline is synchronous to cooperate with Finviz's anti-bot pacing. If profiling shows the page-by-page latency dominates a typical run and Cloudflare tolerates parallel requests, an `httpx`/`aiohttp` rewrite of `fetch_page_sync` is a possibility.

---

## Historical scope (no longer in this codebase)

A previous version of fin_cli bundled a second mode — `fundainsight` — that ran the screener, then enriched each ticker with Yahoo Finance balance-sheet data via `yahooquery` and computed price-to-asset / price-to-current-asset ratios. That mode was removed on 2026-05-04 (see `docs/superpowers/specs/archive/2026-05-04-fincli-only-refactor-design.md`). The git history retains it; anyone who wants to revive the analysis pipeline should fork from the pre-refactor SHA.

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
- **Windows dev environment** — Yonatan works on Windows 11. Path separators, shell quoting (PowerShell vs cmd — e.g. `&` in Finviz URLs needs `python -m fincli "--scrape-link=…"` or the `--%` stop-parsing token), and WSL-awareness matter.
- **Finviz rate limits** — `cfscrape` handles Cloudflare but the screener still rate-limits. `fetch_page_sync` uses exponential backoff; do not remove it.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-24 | **fincli HTTP API mode shipped.** Added `fincli_api/` sibling package exposing the screener over REST+JSON. 9 commits per `docs/features/archive/fincli-api-plan.md`: skeleton + Pydantic models (3-way parallel) + adapter boundary + routes + classifier-driven exception handler (4-way parallel + fix-loop) + 30-test pyramid (unit + integration + 3 live Finviz smoke tests) + committed OpenAPI 3.1.0 snapshot at `docs/api/openapi.{yaml,json}` for polyglot codegen (oapi-codegen, openapi-generator, etc.). The umbrella validates the "fincli is consumable by a downstream pipeline" claim that pipeline-mode + list-filters established — Go/TS/Rust callers can now hit `POST /screens` with `{filters: {fa_pe: "u5", sec: "energy"}}` and receive typed JSON without touching Python. Design spec: `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`. Implementation plan: `docs/features/archive/fincli-api-plan.md`. |
| 2026-05-21 | **Filter inventory dump (`--list-filters --json`) shipped + INTEGRATION.md at root for non-Python integrators.** Closes the polyglot-discoverability gap deferred by pipeline mode (shipped 2026-05-16). Adds `fincli --list-filters --json` — emits a single-line JSON inventory of every Finviz filter (66 keys / ~46 KB) with the `{schema_version, keys, filters: {key: {label, values}}}` shape (CONTRACTS §5.6); the `keys` array is the canonical iteration order for consumers (Go's `encoding/json` randomizes map iteration). Mechanical label derivation in `fincli/resource/params/_label_format.attr_to_label` avoids touching params files' two-element-list contract. New top-level `INTEGRATION.md` covers bootstrap, per-screen call flow, exit-code routing, `OUTPUT_PATH=` recovery, concurrency, and caching for non-Python subprocess consumers. 16 new tests across `tests/unit/resource/params/test_label_format.py`, `tests/unit/app/test_cli_list_filters.py`, and `tests/integration/test_list_filters_output.py`; 0 regressions in the pre-existing 229 cases. Spec moved to `docs/features/archive/list-filters-spec.md` with SHIPPED banner. |
| 2026-05-16 | **Pipeline mode shipped.** Four pillars + two adjacent fixes landed (`docs/features/archive/pipeline-mode-spec.md`): structured filter input (`--filter`/`--filters-json`/`--filters-file` + strict validator + `filter_history.json` writeback fix), deterministic output destination (`--output PATH`/`--output -` + `FINCLI_OUTPUT_DIR`), stream discipline (`--quiet`/`--json-summary` + `OUTPUT_PATH=` discovery line + logger console-stream reroute), differentiated exit codes (0 SUCCESS / 1 INTERNAL / 2 USAGE / 3 UPSTREAM / 4 DATA). Adjacent fixes: `convert_market_cap_to_numeric` rewritten as a nullable `Float64` parser; `Symbol` declared the canonical machine-readable ticker column with a `--output -` carve-out skipping the Excel `=HYPERLINK(...)` wrap. fincli is now usable as a single-shot building block in downstream automation. |
| 2026-05-04 | Single-mode reduction. Removed `fundainsight/` and abandoned scaffolds; retargeted Phase 2 scope to the screener pipeline only. Roadmap "Beyond Phase 4" updated to drop fundamental-analysis aspirations and add the CLI entry-point and Config-driven history follow-ups (`docs/refactoring/`). See `docs/superpowers/specs/archive/2026-05-04-fincli-only-refactor-design.md`. |
| 2026-05-02 | Initial file. Drafted from `CLAUDE.md`, `README.md`, `ARCHITECTURE.md`, and the agent-harness spec. |
