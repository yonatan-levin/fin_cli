# Session Handoff — 2026-05-25

> Supersedes `docs/pendingwork/2026-05-14-session-handoff.md` (pre-HTTP-API). This `docs/pendingwork/` directory is untracked (local-only), so this file lives in the working copy and is not committed.

This session shipped the **fincli HTTP API umbrella** end-to-end (CLI → polyglot-consumable FastAPI service), did a `/docs-update` audit fold-in, and added a Postman collection. Three PRs merged into `master`. There is one unresolved process decision and one big strategic next-step (the Go consumer).

---

## 1. Branch / repo state

- **Current branch:** `master`
- **master HEAD:** `f7edf4c` — `docs(api): add Postman collection for the HTTP API`
- **Working tree:** clean for tracked files. Untracked (expected, gitignored-by-convention): `.codex/`, `docs/pendingwork/`, `uv.lock`.
- **Stale branch needing cleanup:** `feat/fincli-api` (local + `origin/`) — fully merged via PRs #9 and #10, safe to delete. Same post-merge-cleanup pattern as PRs #6/#7/#8. Not yet deleted (see Active Agenda item A2).
- **Tests:** `pytest tests/` → **279 passed / 1 skipped / 3 deselected / 1 xfailed** (~3s). Live tier: `pytest -m live tests/e2e/api/` → **3 passed** (~3s, hits live Finviz). Lint/format clean; `mypy fincli fincli_api` → 0 errors in `fincli_api/`, ~49 pre-existing legacy errors in `fincli/` (Phase-4-deferred baseline, unchanged).

---

## 2. Recently shipped (this session)

### PR #9 — fincli HTTP API umbrella (MERGED, merge commit `b7c9dcd`)

11 commits across 8 task waves + T-FINAL acceptance. Added `fincli_api/` — a FastAPI service exposing the screener over REST+JSON as a second co-equal entry point alongside the CLI. Both consume the same orchestrator (`fincli.app.main.screen_to_dataframe`).

- **T1** (`6db072d`): skeleton + `screen_to_dataframe` helper carved out of `run_stock_screener`.
- **T2** (`04fe46c`): Pydantic models (filters/screens/errors) — 3-way parallel.
- **T3** (`4ee794f`): adapter boundary (`fincli_api/adapters/fincli.py` — ONLY file allowed to import from `fincli/`).
- **T4** (`08c4126`): routes (`/filters`, `/screens`, `/healthz`) + classifier-driven exception handler — 4-way parallel + a BACKEND fix-loop (classifier missing `click.UsageError` branch → 500-not-422; ErrorResponse missing from OpenAPI; pandas `axis=1` regression).
- **T5** (`9480927`): unit + integration test pyramid (30 tests) — 2-way parallel.
- **T5c** (`92bd9e8`): live-Finviz e2e tier (3 tests) + pytest.ini config consolidation.
- **T6** (`e248ede`): committed OpenAPI 3.1.0 snapshot `docs/api/openapi.{yaml,json}` + `scripts/dump_openapi.py --check` drift gate.
- **T7** (`69dd263`): early-docs sweep (CLAUDE/THESIS/FEEDBACK-LOG/README).
- **T8** (`20d8ebf`): post-code docs sweep + spec/plan archive flip; REVIEWER REJECT-loop caught 3 BLOCKERs in INTEGRATION.md (hallucinated `/health`, nested error envelope, CSV content negotiation — none in the real impl), fixed by main-thread fold-in.
- Spec (archived): `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`. Plan (archived): `docs/features/archive/fincli-api-plan.md`.

### PR #10 — /docs-update audit fold-in (MERGED, merge commit `7a7340d`)

Single commit `3fdaf64`. The umbrella's custom-prompt doc-sweeps missed files; running `/docs-update` surfaced **11 stale-content gaps** across 10 files. Fixed: ARCHITECTURE.md (full HTTP-API sweep — was "no server, no network listener"), TOOLS_REFERENCE.md, CLAUDE.md L165, TESTING.md L9 ("zero test bodies" was literally false), CONTRACTS.md L5 ("no REST API"), MODULE_REFERENCE.md L3, agents/roles/{backend-architect,code-reviewer,verifier}.md + agents/rules/scaffold-module.md (stale `tests/domain/` → `tests/integration/`).

### Postman collection (commit `f7edf4c` — DIRECT TO MASTER, see Active Agenda A1)

`docs/api/postman_collection.json` (v2.1.0): 4 requests (healthz, filters, screens-happy, screens-validation-error), `{{baseUrl}}` variable, curated example responses, Newman-runnable test scripts. Verified 15/15 assertions against a live API via a Python httpx harness (Newman's npx install is broken in this env — see Tech Debt T4). Discoverability pointers added to INTEGRATION.md + README.md.

---

## 3. Active agenda (priority order)

### A1 — RESOLVE: Postman commit `f7edf4c` landed direct-to-master (HIGH, ~5 min)

**The one unresolved decision from this session.** PR #10 merged mid-task and silently switched the local checkout to `master`; the Postman commit was made + pushed without branching first, violating the repo's "branch-first on default branch" norm. The commit content is clean (docs-only, verified 15/15). User was asked "leave as-is vs revert + redo via PR" and **did not answer** — they asked for this handoff instead. **Next session: ask the user for the call.** If revert+PR: `git revert f7edf4c` on master OR (cleaner) reset origin/master back to `7a7340d` only if no one else has pulled (risky — prefer revert). If leave: nothing to do; just note the deviation is accepted.

### A2 — Delete stale `feat/fincli-api` branch (LOW, ~2 min)

Fully merged (PRs #9 + #10). `git branch -d feat/fincli-api && git push origin --delete feat/fincli-api`. Trivial housekeeping.

### A3 — Build the Go consumer (HIGH — this is the STRATEGIC next step)

**This is why the HTTP API was built.** The original session goal (before it pivoted to the API) was: a Go project that invokes fincli to get a stock list matching filter criteria, in response to a user request for "detailed market analysis based on features the user is still thinking about." The HTTP API umbrella made fincli polyglot-consumable specifically so this Go consumer can hit `POST /screens` and get typed JSON. **The API side is done; the Go consumer has not been started.** When the user is ready: brainstorm the Go consumer's scope (it was scoped during this session's brainstorming as a separate future spec — see `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md` §N8 "detailed analysis features" deferred). The user's stated near-term scope was "just me via Postman" for the API; the Go consumer is the actual downstream app.

### A4 — Close MAJOR #4: malformed HTML → 200 empty instead of 502 parsing (MEDIUM)

Deferred from the umbrella. When Finviz returns HTML with no `styled-table-new` element (structural drift / anti-bot page), the parser coerces it to a zero-row 200 success instead of a 502 `parsing` error. Fix is parser-level in `fincli/stock_screening/`. **Coordination required:** there's an `xfail(strict=True)` PAIR at `tests/integration/api/test_screens_integration.py` (`test_post_screens_no_table_returns_502_parsing` + `test_post_screens_no_table_current_behavior_returns_200_empty`). Closing MAJOR #4 trips BOTH tests — you must flip/delete both + update docs in the same commit. The xfail's `strict=True` is the forcing function.

### A5 — Fix `ticker_link()` double-slash cosmetic bug (LOW)

`StockTableScreenerParser.ticker_link()` in `fincli/stock_screening/parsers/stock_table.py` produces `https://finviz.com//quote.ashx?t=X` (double slash — `BASE_URL` ends `/`, href starts `/`). Finviz tolerates it; the CLI's Excel HYPERLINK works; the API normalizes to single-slash independently. Pure cosmetic. Fix = strip one slash. Out of scope for everything so far.

---

## 4. Conventions & patterns established this session (preserve these)

- **plan-and-create per-wave discipline scaled cleanly to 11 commits**: BACKEND → VERIFIER → REVIEWER → QA → HUMAN gate per wave, with parallel BACKEND dispatch (`superpowers:dispatching-parallel-agents`) where tasks were independent (T2 3-way, T4 4-way, T5 2-way, T7' 4-way, T8 6-way). Zero file conflicts because each parallel agent owned a distinct write surface; shared files (`__init__.py`, `main.py` wiring) were batched by the main thread after the parallel agents landed.
- **2 REVIEWER REJECT-loops both recovered cheaply** (T4 classifier/OpenAPI/pandas BLOCKERs via BACKEND fix-loop; T8 INTEGRATION.md doc-vs-code drift via main-thread fold-in). REVIEWER's cross-file consistency check caught what per-file VERIFIER structurally couldn't.
- **Live-e2e is now a mandatory pre-HUMAN gate** for any change to `fincli_api/` or `fincli/stock_screening/`. Rationale: the original screener bug (1-page IndexError) shipped because mocked tests didn't exercise the live path. Captured in FEEDBACK-LOG 2026-05-22 + 2026-05-24.
- **`/docs-update` lesson (the big process takeaway):** custom-prompt doc-sweeps are SUPPLEMENTARY, not a replacement for the `/docs-update` skill. Invoke `/docs-update` at the end of ANY umbrella that touches public surfaces — it has a curated file checklist that catches docs the manual prompt enumeration forgets (this session, it caught ARCHITECTURE.md + TOOLS_REFERENCE.md + agents/ files + 4 stale intro-lines the umbrella missed). Captured in PR #10's commit body.
- **Mock-target rule (load-bearing for any future API/screener test):** patch `fincli.app.main.fetch_page_sync`, NOT `fincli.utils.web_scraper.fetch_page_sync`. The former is the local-name binding via `from ... import`; patching the original location doesn't affect what `main.py` already imported. Documented in `tests/integration/api/conftest.py`.
- **pytest.ini is canonical** (NOT `pyproject.toml [tool.pytest.ini_options]`). Pytest precedence picks pytest.ini first; pyproject's section was stripped to a comment in T5c. Don't reintroduce.
- **Archive convention:** shipped specs → `docs/superpowers/specs/archive/`; shipped plans → `docs/features/archive/`. Add a SHIPPED banner, sweep all live cross-references to the archive path (skip refs inside `archive/` — historical), do the `git mv` + ref-sweep in ONE commit.

---

## 5. Auto-memory pointers

- Memory dir: `C:\Users\Yonatan Levin\.claude\projects\C--Users-Yonatan-Levin-Documents-Programming-Projects-FinTech-Strade-algo-beta\memory\`
- `MEMORY.md` index references: project_overview.md, project_tech_debt.md, user_yonatan.md (these predate the HTTP API; project_overview.md may be worth updating to mention the two-entry-point identity — LOW priority).
- Durable cross-cutting decisions live in `docs/FEEDBACK-LOG.md` (2026-05-22 screener-fix entry + 2026-05-24 umbrella-patterns entry — 5 patterns: mock-target, validator-first ordering, single-source classifier extension, pytest.ini canonical, xfail-pair).

---

## 6. How to resume immediately (first actions for next session)

1. **Confirm branch state:** `git checkout master && git pull && git log --oneline -5` — expect `f7edf4c` at HEAD (unless A1's revert decision changed it).
2. **Ask the user about A1** (the direct-to-master Postman commit — leave or revert+PR?) and **A2** (delete stale `feat/fincli-api`?). These are the two open loops from this session.
3. **Sanity-check the API still runs:** `uvicorn fincli_api.main:app --reload` then `curl localhost:8000/healthz` + browse `localhost:8000/docs`. Or `pytest -m live tests/e2e/api/` for the full live gate.
4. **If the user wants to move forward strategically → A3 (Go consumer).** Invoke `superpowers:brainstorming` first (it's "build X" creative work). The API contract it consumes is locked: `docs/api/openapi.yaml` + `CONTRACTS.md` §8 + `INTEGRATION.md` "HTTP API mode". The Go consumer codegens a typed client from the OpenAPI snapshot.
5. **If the user wants to clean up tech debt → A4 (MAJOR #4, with the xfail-pair coordination) or A5 (ticker_link slash).**

### Verification one-liners

```bash
pytest tests/                              # 279 passed / 1 skipped / 3 deselected / 1 xfailed
pytest -m live tests/e2e/api/              # 3 passed (live Finviz)
python scripts/dump_openapi.py --check     # exit 0 (OpenAPI snapshot not drifted)
ruff check . && ruff format --check .      # clean
mypy fincli fincli_api                     # fincli_api 0 errors; fincli ~49 legacy baseline
uvicorn fincli_api.main:app --reload       # then localhost:8000/docs for Swagger UI
```
