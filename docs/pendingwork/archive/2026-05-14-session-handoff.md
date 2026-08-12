# Session Handoff — Post Multi-Cycle Sprint

**Date:** 2026-05-14
**Branch:** `refactor/fincli-only`
**HEAD:** `930f05d` — `fix(cli): restore --scrape-link option lost in single-mode refactor`
**Working tree:** clean (only untracked `.codex/`, gitignored)
**Pushed:** yes, in sync with `origin/refactor/fincli-only`

This is a context handoff for resuming work cleanly. Read this end-to-end before touching anything; it captures the multi-session sprint that just completed and the agenda that's queued.

---

## 1. Where we are

The `refactor/fincli-only` branch is **6 commits ahead of master**, all pushed. The branch was bootstrapped during a multi-day sprint that:

- Replaced the project's two-mode (screener + fundamental analysis) layout with a single-mode Finviz screener CLI under `fincli/`
- Established the agent-harness workflow (BACKEND / VERIFIER / REVIEWER / QA subagent dispatch + skill-driven cycles)
- Resolved 5 of the 8+ open tech-debt items
- Seeded the project's first real pytest test bodies

### Recently shipped commits (newest first)

| Commit | Subject | Cycle |
|---|---|---|
| `930f05d` | `fix(cli): restore --scrape-link option lost in single-mode refactor` | 2026-05-13 — `/debug` |
| `94f50e7` | `feat(config)!: resolve history_dir via platformdirs + HISTORY_DIR env override` | 2026-05-11 — `/plan-and-create` |
| `743bd29` | `refactor(config): expose history directory as Config.history_dir field` | 2026-05-09 — `/plan-and-create` |
| `a4a0bdc` | `chore(docs): remove abandoned-direction docs (M1/L1/L2 sweep + projectspec.mdc)` | 2026-05-09 — `/docs-update` |
| `d398111` | `chore: remove abandoned finpack library surface (50 files, -6070 LOC)` | 2026-05-08 — `/debug` |
| `7225bb1` | `feat(packaging): expose \`fincli\` as a console-script entry point` | 2026-05-06 — `/plan-and-create` |

### Live verification of latest state (2026-05-13)

The `--scrape-link` regression fix was end-to-end verified by running the user's exact original bug-report URL against live Finviz: 135 stock rows fetched across 8 paginated pages in ~6 seconds, CSV written to `workspace_output/stock_screener_2026-05-13_20-37.csv` with all 12 documented columns. The bug is **provably fixed in production**.

### Current baselines (from 2026-05-13 verification)

- Ruff: **195 errors** (down 4 from 199 pre-sprint baseline)
- Format: **20 files would reformat** (down 1)
- Mypy strict: **60 errors / 15 files** (down 3 from 63)
- Pytest: **2 passing, 0 errors** (up from "no tests today, no collection errors" pre-sprint)

---

## 2. Active agenda

Three substantive items queued, in priority order I'd defend. Pick freely — user has final call.

### Item 1 — Phase 2 tests (LARGE — multi-session commitment)

**The strategy is already settled by the user**: adaptive multi-scope e2e ("slicing"). Full e2e for happy paths + section-scoped e2e for pipeline slices. 90% coverage target. No trivial unit tests. See `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` for the rollout context.

**First-cycle scope (when this gets actioned)** — ARCH-only:
- Decompose the screener pipeline into testable slices (URL builder, HTML parser content/parsers/locators, DataFrame builder, market-cap converter, interactive UI, configurator)
- Decide test-data strategy: HTML fixtures committed to `tests/fixtures/` (one fixture per parser scenario), HTTP cassettes via `vcrpy` or `responses` for cfscrape mocking
- Decide conftest.py layout: shared `mock_logger`, `tmp_history_dir`, etc.
- Sequence the cycles: which slice first? URL builder is the obvious starting point (pure function, no external deps, easy fixtures)

**Why this matters strategically:** Phase 2 unlocks Phase 3 (coverage gate at 90% in `.claude/hooks/on-stop.js`) and Phase 4 (mypy promotion from `warnings` to `issues` channel). It's the gravitational center of the harness rollout.

**Cost:** Probably 2-4 cycles minimum to reach 90%. First cycle would be ARCH-only (the test infrastructure design); BACKEND cycles follow.

### Item 2 — `--set-filters` sibling restoration (SMALL — mirrors yesterday's cycle)

The sibling Click option lost in the same commit (`a840a1c`) as `--scrape-link`. The historical fundainsight CLI had `@click.option('--set-filters', default="", help="...")` that took a JSON filter string. It populated `Config.filters` via `core/converters/json.py:json_to_tuples`. The `filters` parameter on `build_config(use_history, filters, scrape_link)` already accepts the JSON string (verified — already plumbed); only the CLI option to feed it is missing.

**Use yesterday's `--scrape-link` cycle as the template** — same shape, smaller scope:
- ARCH spec under `docs/features/set-filters-restoration-spec.md`
- BACKEND adds `@click.option('--set-filters', default="", ...)` to `run_main`
- Threads `set_filters` → `build_config(filters=set_filters)` → `Config.filters`
- Add regression test to `tests/unit/app/test_cli.py` (grows the seed test corpus)
- Mutual exclusion question: should `--set-filters` be mutually exclusive with `--history` and `--scrape-link`? My read: yes — three alternative input modes, only one should be active. The mutual-exclusion check in `run_main` becomes a three-way constraint instead of two-way.

**Reviewer note status:** I have NOT opened `docs/reviewer/set-filters-restoration.md` yet. If you want it tracked formally before actioning, dispatch /plan-and-create.

### Item 3 — `scripts/check_requirements.py` `pkg_resources` regression (TINY — 15 minutes)

The launcher precheck prints a Python-3.12-incompatibility traceback on every `./run.bat` / `./run.sh` invocation:
```
AttributeError: module 'pkgutil' has no attribute 'ImpImporter'
```

`pkg_resources` (provided by setuptools) uses `pkgutil.ImpImporter`, which was removed in Python 3.12. The launcher falls through to `pip install -r requirements.txt` so it doesn't actually break anything — just adds noise on every run.

**Fix (single file rewrite):**
- Replace `pkg_resources.require(open('requirements.txt').readlines())` (or equivalent) with `importlib.metadata.distributions()` + `packaging.requirements.Requirement`
- No new deps — `packaging` is already a transitive dep of setuptools
- No contract change — same input (`requirements.txt`), same exit code semantics

**Verification:** run `./run.bat --help` and confirm no traceback in stderr.

**This is the cleanest interleave between bigger cycles** — 15 minutes including verification, immediate quality-of-life improvement.

---

## 3. Minor cleanups (drop-in any time)

| Item | Effort | Notes |
|---|---|---|
| `.codex/` untracked dir | 1 line in `.gitignore` | Tool artifact from a parallel IDE running alongside Claude. Shows up in every `git status`. Three options: gitignore, track, or delete. Need user decision. |
| `git remote set-url` for redirect warning | 1 command | `git remote set-url origin https://github.com/yonatan-levin/fin_cli.git` to silence the "repository moved" notice on every push. Can't do autonomously — per system rules, never update git config without explicit user ask. |
| 20 ruff format-drift files in `tests/` legacy | Optional bulk-fix | All pre-existing format drift in `tests/__pycache__/` corners and legacy scaffolds. Not introduced by recent work. `ruff format .` would close it but expands scope. |

---

## 4. Workflow patterns established this sprint

The user has consistently preferred these patterns. Future-Claude should adopt them by default rather than asking:

### Validation cycle is non-negotiable

Every substantive change goes through: **BACKEND → VERIFIER → REVIEWER → QA → HUMAN**. The user explicitly said for V/R/Q: **dispatch as subagents** (not in-thread). BACKEND is usually a subagent too, but tiny mechanical fixes (1-token edits, single-line nits) get done inline — the user has greenlit "do them yourself" for those.

### ARCH placement: inline vs file

- **Small scope** (<10 LOC change, <5 files): inline-ARCH in chat. Skip writing a spec file.
- **Medium scope** (≥10 LOC, multi-file, new feature surface): write the spec to `docs/refactoring/<topic>-spec.md` (refactors) or `docs/features/<topic>-spec.md` (features), expand → BACKEND.
- **Lifecycle**: spec file → BACKEND → shipped → move to `<dir>/archive/` with Shipped banner. Same banner format across all archive dirs.

### Skill dispatch heuristics

- User-reported bug → `/debug` (mandatory QA triage first, then BACKEND)
- New feature or restoration → `/plan-and-create` (ARCH first)
- Doc-rot sweep after major changes → `/docs-update`
- Pre-push gate → fresh verification (Iron Law from `verification-before-completion`) + `/security-review` if substantial

### Commit conventions

- **Conventional commits**: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:` with scope (`(config)`, `(packaging)`, `(cli)`).
- **Breaking changes** flagged with `!` (e.g., `feat(config)!:`) AND a `BREAKING CHANGE:` footer per CONTRACTS §7.
- **Co-Authored-By trailer**: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` on every Claude-assisted commit.
- **Detailed commit bodies**: this project's culture is multi-paragraph commit bodies that capture why + what + verification + follow-ups. The /debug and /plan-and-create REVIEWER agents draft these.

### Documentation cross-reference style

- **CONTRACTS.md §<N>** is the *single source of truth* for stable surfaces (CLI options, Config fields, function signatures, CSV schema). Other docs (`README.md`, `ARCHITECTURE.md`, `docs/MODULE_REFERENCE.md`) refer to CONTRACTS abstractly with `(see CONTRACTS §X.Y)` cross-refs instead of duplicating literal values.
- **`<Config.field>` placeholder**: when describing runtime-resolved values in narrative docs, use angle-bracketed placeholders rather than republishing platform-specific paths.
- **FEEDBACK-LOG is append-only**: prior-date entries are immutable historical record. Only *forward-progress* entries get added.

### Env-var naming convention

`UPPER_CASE_WITH_UNDERSCORES`, **no project prefix**. Matches the existing `USE_HISTORY`, `HISTORY_DIR`. No `FINCLI_` prefix. The user confirmed this in the CWD-portability cycle.

### When grepping for stale references

Include `.mdc` (Cursor rules) and `.md` (Markdown) and `.mdx` if present. The 2026-05-09 stale-docs sweep missed `.cursor/rules/projectspec.mdc` because the initial grep pattern was `.md`-only.

---

## 5. Auto-memory entries to consult

Located at `C:\Users\Yonatan Levin\.claude\projects\C--Users-Yonatan-Levin-Documents-Programming-Projects-FinTech-Strade-algo-beta\memory\`:

- **`project_tech_debt.md`** — last updated 2026-05-13 post-`--scrape-link` cycle. Lists the three active items above plus established conventions.
- **`project_overview.md`** — high-level project description (likely stale; verify against current CLAUDE.md before relying).
- **`user_yonatan.md`** — user profile (FinTech developer, Windows 11, prefers comprehensive docs, hands-on at decision points, efficient with cycle management).

---

## 6. How to resume immediately

If next session opens with "continue from where we stopped":

1. **Read this file** end-to-end.
2. **Read `CLAUDE.md`** Phase Status section to confirm current phase (Phase 1, with mypy/coverage gates still advisory).
3. **Read `docs/FEEDBACK-LOG.md`** entries from 2026-05-04 onward — captures every design decision made this sprint.
4. **Check `git log --oneline -10`** — confirm the 6-commit sprint head matches `930f05d`.
5. **Ask the user** which agenda item to start: 1 (Phase 2 — big), 2 (`--set-filters` — small mirror), or 3 (`check_requirements.py` — tiny). Or surface a different priority if the user has one.

---

## 7. Open decisions deferred to the user

These came up during the sprint but were never fully closed:

- **`.codex/` handling** — gitignore, track, or delete? Still untracked, still showing in every `git status`.
- **`git remote set-url`** to fix the "repository moved" redirect — user knows about it; never run.
- **`--set-filters` priority** — restore as Item 2 above, or skip entirely (the JSON-filter-string input mode was niche)?
- **Phase 2 first-cycle scope** — start with URL builder (pure-function, easiest fixtures) or interactive UI (highest-coverage slice)? Asked but not answered.
- **`--history-dir` CLI flag** — explicitly rejected in the CWD-portability cycle ("env var is sufficient"). If usage patterns reveal a real need for an interactive override, revisit.

---

## 8. What worked well this sprint (worth preserving)

- **QA-driven triage** — every /debug cycle started with QA finding the root cause via `git log -S` and `git diff -p`. This made BACKEND's work mechanical, not investigatory.
- **Subagent independence** — VERIFIER catching `appauthor=False` doubled-path (Windows-specific issue) by running real platformdirs queries. The independent re-verify lens caught what in-thread verification would have missed.
- **REVIEWER cumulative perspective** — first agent to read the *whole* doc cascade as a unit; caught contradictions VERIFIER didn't (e.g., CONTRACTS §4.1 vs §4.2 internal contradiction during CWD-portability cycle round 1).
- **Inline ARCH for small cycles** — established that the user trusts you to ARCH small cycles inline rather than dispatching a full subagent. Saves a turn.
- **Live end-to-end verification at the end** — the user asked for "run live test" only at the very end of yesterday's cycle. Worth doing proactively whenever a network-dependent feature is touched.

---

End of handoff. Next session can start cold with this file as orientation.
