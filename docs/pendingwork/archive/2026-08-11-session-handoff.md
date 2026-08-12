# Session Handoff — 2026-08-11 — Close ALL open gaps (GitHub + docs/)

> **CLOSED 2026-08-12.** All items 0–7 executed: master was already pushed
> (item 0); parser hardening merged via PR #17 (issue #14 closed, MAJOR #4
> resolved); `scrape_link` merged via PR #18 (orchestrator #17/#19 notified);
> docs/lifecycle closure merged via PR #19 (plus a discovered-and-fixed
> `fincli_api` mypy-scope regression); `dev` deleted after tagging
> `archive/dev-fundainsight-2025-09` (owner-approved); pendingwork archived
> per lifecycle. Archived as a historical record.

> Project: **algo_beta / fin_cli** (`yonatan-levin/fin_cli`)
> Written from: post-merge cleanup session (observability + product-README merges
> concluded, branches deleted). Supersedes nothing — this is the consolidated
> burndown of every open item found in GitHub and the `docs/` tree as of today.
> Mission for the next session: **work through items 0–7 below and close them all.**

---

## 1. Branch / repo state (as of 2026-08-11)

- **Local `master` HEAD:** `6ee7093` — `Merge branch 'feat/observability'`.
- **`master` is 7 commits AHEAD of `origin/master` and NOT pushed.** Those 7
  commits include the entire observability stream (4 commits + merge) and the
  product-README rewrite. The remote branch `feat/observability` was already
  deleted, so **local master is currently the only copy of that work anywhere**.
  Pushing is item 0 — do it first.
- **Local branches:** `master`, `dev` (unmerged, stale — see item 6).
- **Remote branches:** `master`, `dev`, `docs/handoff-2026-07-28` (unmerged;
  sole content = the issue-#14 handoff doc, byte-identical to the local
  untracked copy in `docs/pendingwork/`).
- **Working tree:** clean for tracked files. Untracked as usual:
  `docs/pendingwork/`, `uv.lock`.
- **Quality gates (verified today on master):** Ruff clean, `ruff format` clean,
  strict mypy clean (48 files), **310 passed + 1 xfail**, coverage **94.13%**
  (blocking gate 90%). The xfail is the documented MAJOR #4 deferral (item 3).

---

## 2. The open items (work them in this order)

### Item 0 — Push master (URGENT, 1 minute)
`git push` from the primary checkout. Until this happens the observability
merge exists only on this machine. Everything else can wait; this cannot.

### Item 1 — Issue #14: duplicated-first-letter ticker parse (HIGH)
- **GitHub:** [#14](https://github.com/yonatan-levin/fin_cli/issues/14) — OPEN,
  labels `bug`, `planning`. The only open issue; there are no open PRs.
- **Full handoff:** `docs/pendingwork/2026-07-28-handoff-ticker-duplicated-first-letter.md`
  (also pushed as remote branch `docs/handoff-2026-07-28`).
- **Symptom:** every parsed ticker gets its first letter duplicated (`KKTOS`
  for KTOS, `BBABA` for BABA) on the redesigned Finviz layout — in BOTH
  `POST /screens` `stocks[].ticker` and the CLI CSV `Symbol` column — and it
  fails **silently** (exit 0 / HTTP 200 with corrupted data). The anchor href
  (`stock?t=KTOS&...`) still holds the truth; consumers currently work around
  via the href.
- **Likely cause:** redesigned row markup nests an icon/logo `<span>` inside the
  ticker cell, so cell-text extraction concatenates two text nodes.
- **Key code:** `fincli/stock_screening/parsers/stock_table.py`,
  `fincli/stock_screening/content/stock_table.py`,
  `fincli/stock_screening/locators/stock_table_locators.py`,
  `fincli/app/exit_codes.py`.
- **Acceptance (from the issue):**
  - [ ] Tickers parse correctly on the current layout (fixture captured from live HTML).
  - [ ] Contract test: anchor-href vs cell-text mismatch FAILS the parse
        (exit 4 / `error_class: parsing`) instead of passing corrupted data.
  - [ ] Regression test with the redesigned-layout fixture.
- **After it ships:** close #14 with a resolution comment; delete remote branch
  `docs/handoff-2026-07-28` and archive its doc (item 7).

### Item 2 — Change request: `scrape_link` on `POST /screens` (consumer-blocking)
- **Doc:** `docs/pendingwork/2026-07-25-scrape-link-http-api.md` — **Status: OPEN**.
- **Ask:** accept `{"scrape_link": "<finviz screener URL>"}` on `POST /screens`,
  mutually exclusive with `filters`, same semantics as CLI `--scrape-link`
  (fetch verbatim, no inventory validation, don't overwrite `filter_history.json`).
- **Why:** two filters in the owner's frozen screen (`fa_sales3years_pos`,
  `ta_perf2_3yup`) have no inventory key; the 7-filter subset overcounts 2.2×
  (227 vs 101 rows). Orchestrator issues
  [strade-orchestrator#17](https://github.com/yonatan-levin/strade-orchestrator/issues/17) and
  [#19](https://github.com/yonatan-levin/strade-orchestrator/issues/19) depend on it;
  today the orchestrator shells out to the CLI instead of using HTTP.
- **Scope notes:** touches `fincli_api/models/screens.py` (request model +
  mutual exclusion), `fincli_api/routes/screens.py`,
  `fincli_api/adapters/fincli.py` (the ONLY file allowed to import `fincli`),
  OpenAPI snapshot regen (`python scripts/dump_openapi.py`), INTEGRATION.md +
  CONTRACTS.md. Complementary-but-not-substitute: add the 2 missing inventory keys.
- **After it ships:** mark the CR doc SHIPPED/archive it; comment on the two
  orchestrator issues so they can flip to HTTP mode.

### Item 3 — Deferred MAJOR #4: malformed HTML → 200 empty instead of 502 parsing
- **Where documented:** `fincli_api/exception_handlers.py` module docstring;
  xfail pair at `tests/integration/api/test_screens_integration.py`
  (`test_post_screens_no_table_returns_502_parsing`); CLAUDE.md gotcha.
- **Gap:** HTML with no `styled-table-new` element routes through the zero-row
  success branch (200, empty stocks) instead of spec §5.1's 502 `parsing`
  envelope. Closing requires parser-level changes in `fincli/stock_screening/`.
- **Do it WITH item 1:** the fail-loudly acceptance of #14 is the same
  fail-loudly principle here, in the same parser layer — one coordinated parser
  hardening pass closes both. Flip the xfail pair to a plain passing test when done.

### Item 4 — Doc-truth fix: THESIS.md still claims "local-only, no remote tracker"
- `docs/THESIS.md:118`: "**Local-only project** — no remote issue tracker."
  False since at least 2026-06-27: origin is
  `https://github.com/yonatan-levin/fin_cli.git`, gh is authenticated, and
  issue #14 lives there. Reconcile the sentence (GitHub issues + docs trackers
  both exist; state which is canonical for what). Known discrepancy since the
  2026-06-27 session; never fixed.

### Item 5 — Lifecycle closure: harness-burndown spec/plan shipped but never archived
- `docs/refactoring/spec/harness-quality-gates-burndown-spec.md` still says
  **"Status: READY FOR IMPLEMENTATION"** with 21 unchecked boxes;
  `docs/refactoring/implementations/harness-quality-gates-burndown-plan.md` has
  82 unchecked boxes. But the work SHIPPED: commits `0d90ef8` (strict-mypy zero,
  94% coverage), `7c59fb6` (blocking gates), `db93430` (doc roles + CHANGELOG),
  merged in `d46afda`, follow-up fix `05a1536`; today's gate run confirms the
  end state (94.13% aggregate, mypy zero, blocking hooks).
- **Action:** verify each spec requirement is actually satisfied (spot-check, not
  blind-tick), update the status banner to SHIPPED, and move both files to
  `docs/refactoring/archive/` with an inbound-link sweep — the terminal-lifecycle
  rule that spec itself established. Same pass: decide whether
  `docs/plans/2026-07-14-observability.md` (now merged) gets a SHIPPED banner /
  archive location, honoring its documented follow-up (full CLI log correlation
  through the Singleton logger was an explicit non-goal → still open as a
  future item; keep that visible, e.g. one line in THESIS "Beyond Phase 4").

### Item 6 — Decision: the `dev` branch
- `dev` (`b8825d9`, tracks `origin/dev`) predates the June–August streams and is
  unmerged into master ("merge recent changes before consolidating the lib
  code"). Diff it against master; almost certainly superseded by the fincli
  refactor. **This is an owner decision** — present the diff summary and
  recommend keep/delete; delete local + remote only on explicit approval.

### Item 7 — Housekeeping: pendingwork lifecycle
Per `docs/pendingwork/README.md`, superseded handoffs move to
`docs/pendingwork/archive/`:
- `2026-05-14-session-handoff.md` and `2026-05-25-session-handoff.md` — long
  superseded (their agenda items: fincli-api shipped, branch cleanup done
  2026-06-28) → archive now.
- `2026-07-25-scrape-link-http-api.md` → archive when item 2 ships.
- `2026-07-28-handoff-ticker-duplicated-first-letter.md` → archive when item 1
  ships; then delete remote branch `docs/handoff-2026-07-28`.
- This file → archive when items 0–6 are closed.

---

## 3. Conventions the next session must honor

- **Worktree always** — never edit on the primary checkout; branch per item
  (`fix/`, `feat/`, `docs/` prefixes), commits scoped to the task's files only
  (never `git add -A`; untracked `uv.lock`, `docs/pendingwork/`, `.codex/` roam
  the tree).
- **Gates are blocking:** Ruff + format + strict mypy + pytest with ≥90%
  aggregate coverage (`on-stop.js` enforces). Run them per change, not once at the end.
- **Adapter boundary:** `fincli_api/adapters/fincli.py` stays the only
  `fincli_api` → `fincli` import.
- **Contract discipline:** any `POST /screens` change regenerates
  `docs/api/openapi.{yaml,json}` (`python scripts/dump_openapi.py`) and updates
  INTEGRATION.md/CONTRACTS.md in the same PR.
- **Fail loudly:** exit 4 / `error_class: parsing` for unparseable layouts —
  never exit 0 with corrupted data (the moral of both item 1 and item 3).
- **Mock `fincli.app.main.fetch_page_sync`** (the orchestrator's local binding),
  not the definition in `fincli.utils.web_scraper`.
- Live-Finviz verification tier: `pytest -m live tests/e2e/api/` — mandated
  pre-PR for `fincli_api/` and `fincli/stock_screening/` changes.

---

## 4. Suggested execution order

```
0. git push (primary checkout, master)               [1 min, unblocks everything]
1+3. Parser hardening branch: fix #14 + close MAJOR #4  [the real work; live fixture first]
2. scrape_link on POST /screens                      [independent; can parallel 1+3]
4. THESIS local-only correction                      [tiny; fold into any docs PR]
5. Burndown spec/plan verify + archive               [docs-only PR]
6. dev-branch diff + owner recommendation            [read-only + a question]
7. pendingwork archive sweep                          [local-only, no PR needed]
```

Items 1+3 and 2 both touch `POST /screens` behavior/docs — land 1+3 first or
keep the branches rebased; both regenerate the OpenAPI snapshot.

---

## 5. Starting prompt for the next session

Copy-paste this to start the burndown session:

```
Read docs/pendingwork/2026-08-11-session-handoff.md end-to-end before touching
anything — it is the consolidated burndown of every open gap in this repo
(GitHub + docs/), and this session's mission is to close ALL of them.

Then execute its §4 order:
0. Push master to origin first (it is 7 commits ahead and holds the only copy
   of the observability merge).
1. Fix issue #14 (duplicated-first-letter ticker parse) together with the
   deferred MAJOR #4 (malformed HTML must return the 502 parsing envelope, not
   200-empty) as one parser-hardening stream: capture a live-HTML fixture
   first, enforce href-vs-cell-text agreement, fail loudly (exit 4 /
   error_class parsing), flip the xfail, close #14 on GitHub.
2. Implement the open change request: scrape_link on POST /screens (doc:
   docs/pendingwork/2026-07-25-scrape-link-http-api.md), regenerate the
   OpenAPI snapshot, update INTEGRATION.md/CONTRACTS.md, then comment on
   strade-orchestrator issues #17 and #19.
3. Fix docs/THESIS.md:118 ("local-only, no remote tracker" is false).
4. Verify + archive the shipped harness-burndown spec/plan
   (docs/refactoring/), and give the merged observability plan its terminal
   lifecycle state, keeping its documented CLI-log-correlation follow-up visible.
5. Diff the stale dev branch vs master and give me a keep/delete
   recommendation — do not delete without my approval.
6. Archive superseded docs/pendingwork/ handoffs per its README lifecycle.

Rules: every change in its own worktree + branch, scoped commits, all gates
green per change (Ruff, format, strict mypy, pytest ≥90% aggregate coverage),
live-Finviz tier (pytest -m live) before any parser/API PR, OpenAPI snapshot
regenerated with any /screens change. Open a PR per stream; do not merge to
master without me. Work autonomously through the list; only stop for the dev-
branch decision and PR merges.
```

---

## 6. Auto-memory pointers

- claude-mem observations cover: today's merge-conclusion + branch cleanup
  (2026-08-11), the 2026-06-28 branch sweep, the 2026-06-27 launcher removal +
  worktree-always decision, and the 2026-07-18 DCF-bug session that produced
  items 1 and 2. Search terms: "observability merge", "ticker duplicated",
  "scrape_link HTTP API", "branch cleanup".
