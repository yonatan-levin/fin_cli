# Fincli-Only Refactor — Design Specification

**Version:** 1.3
**Date:** 2026-05-04
**Status:** APPROVED FOR IMPLEMENTATION
**Author:** yonatan (decisions); ARCH (formalization)
**Mode:** REFACTOR (scope reduction; deletion-heavy with one one-line code fix plus two follow-through commits authorized in v1.2 plus one CLI bug-fix commit authorized in v1.3)
**Amendments:**
- 2026-05-04 (v1.1) — applied five hardening amendments after gpt-5.5-pro adversarial review of v1.0 (clean-venv non-importability evidence, phrase-level docs grep, mypy baseline citation softened, tracked-automation audit added to Commit 1, classification clarifier §3.0 added). See §3.0, §3.1 (Commit 1 sub-bullet via §5.1), §7.2 verification table additions, and §11.1 A3.
- v1.2 (2026-05-04): Commits 10–11 added (R3 hook retargeting, setuptools auto-discovery fix). A2 dropped; R3 closed.
- v1.3 (2026-05-04): Commit 13 added (CLI section-prompt + bounds-checked input fix, post-validation scope expansion). §2.2 N4 narrowed to acknowledge the exception. §3.2 edit table extended. §10 Behavior criterion appended with the section-by-section sub-bullet.
**Companion specs:**
- `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` (Phase 1 harness — historical)
- `docs/refactoring/cli-entry-point-spec.md` (deliverable of this refactor — future work)
- `docs/refactoring/history-path-config-spec.md` (deliverable of this refactor — future work)

---

## 1. Summary

Reduce `algo_beta` to a single-mode CLI: just the Finviz screener under `fincli/`. The `fundainsight/` fundamental-analysis module and all abandoned scaffolds (`wisdom_fruit/`, `shared/`, `example/`, `src/`, `benchmarks/`) are removed. Shared infrastructure (`core/`, `config/`, `logger/`, `singleton.py`) and the freshly-installed agent harness (`agents/`, `.claude/`, `docs/`) are preserved. Top-level docs are rewritten in full as if `algo_beta` had always been a single-mode screener — no future reader should be able to tell this used to be a two-product repo.

One load-bearing one-line code fix is required (`core/configuration/configurator.py:17`: literal `'fundainsight'` -> `'fincli'`). It must land **before** `fundainsight/` is deleted, otherwise `fincli --history` raises `FileNotFoundError` in any intermediate snapshot.

---

## 2. Requirements

### 2.1 Goals

- **G1** `algo_beta` builds, installs, and runs `python -m fincli` end-to-end after the refactor with no references to `fundainsight` or `yahooquery` in source, configuration, or documentation.
- **G2** The `fincli --history` flag reads/writes `fincli/local_history/filter_history.json` (regression-fixed today; clean implementation in a follow-up spec).
- **G3** Project metadata is honest: `pyproject.toml` ships as `name = "fincli"` with `yahooquery` removed; `requirements.txt` mirrors that change while keeping the `urllib3<2` pin needed by `cfscrape`.
- **G4** Top-level documentation reads as a fresh single-mode CLI spec. Two-mode tables collapse to plain prose; section structure may change. `docs/FEEDBACK-LOG.md` remains append-only and gets one new dated entry.
- **G5** The agent harness (`agents/rules/*`, `agents/roles/*`, `.claude/hooks/`) is fully retargeted to the single-mode reality. The harness rollout spec (`2026-05-02-agent-harness-replication-design.md`) is preserved as historical record with a one-line banner pointing at this spec.
- **G6** Two follow-up specs are created at `docs/refactoring/cli-entry-point-spec.md` and `docs/refactoring/history-path-config-spec.md` capturing deferred work (entry-point wiring; Config-driven history path).

### 2.2 Non-Goals

- **N1** Adding a `[project.scripts]` entry point. Captured as future-work in `docs/refactoring/cli-entry-point-spec.md`.
- **N2** Migrating the `--history` filter-cache path into `Config`. Captured as future-work in `docs/refactoring/history-path-config-spec.md`.
- **N3** Introducing pytest test bodies. Phase 2 of the harness rollout owns that work; this refactor only retargets it from `fundainsight/calculators/` to `fincli/stock_screening/` + the screener pipeline.
- **N4** No other source code edits, **except** the §3.2 configurator one-liner (Commit 2) and the §5.1 Commit 13 CLI section-prompt fix. The latter was added in v1.3 after the v1.2 validation cycle completed and live happy-path testing surfaced a pre-existing display+parser mismatch in `fincli/cli/cli_stock_screener.py` that had to be fixed for §10 Behavior acceptance to be reachable. No migration or preservation of the deleted `fundainsight` logic is offered.
- **N5** Bumping `urllib3` past `2.x`. The pin is still required by `cfscrape` and stays.
- **N6** Touching the harness rollout spec body. Banner-only edit.
- **N7** Cutting a release / version bump. The codebase is source-only; no PyPI publication.

### 2.3 Constraints

- **Commit ordering is load-bearing.** The configurator one-liner must precede the `fundainsight/` deletion to avoid breaking `fincli --history` in any intermediate snapshot.
- **`docs/FEEDBACK-LOG.md` is append-only.** Past entries must not be edited; one new dated entry is appended.
- **`Phase Status` and `Tech Debt` sections of `CLAUDE.md`** require surgical updates beyond the broader rewrite — see §6.3 for exact deltas.
- **Verification grep results are part of acceptance.** `grep -r "fundainsight"` must return only the harness rollout spec banner; `grep -r "yahooquery"` must return nothing. (See §8 verification checklist.)
- **No public CLI surface change for `fincli`.** The `fundainsight` CLI is removed entirely; that is a deliberate removal of a public surface, not a rename.

### 2.4 Success Criteria (Checklist)

- [ ] `python -m fincli --debug` runs to completion against Finviz; produces `workspace_output/stock_screener_*.csv`.
- [ ] `python -m fincli --history` reads from `fincli/local_history/filter_history.json` (creates the directory if missing).
- [ ] `pip install -e ".[dev]"` from a clean venv installs the project as `fincli` (not `finscrape`).
- [ ] `python -c "import fincli; import core; import config; import logger; import singleton"` succeeds.
- [ ] `ruff check .` exits 0.
- [ ] `ruff format --check .` exits 0.
- [ ] `mypy fincli core config logger` reports same-or-fewer errors than the pre-refactor baseline (still advisory in Phase 1).
- [ ] `pytest tests/` exits 0 (no test bodies; collects nothing).
- [ ] `grep -r "fundainsight" .` (excluding `.git`, `node_modules`, `workspace_output`, `__pycache__`) returns only the banner line in `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.
- [ ] `grep -r "yahooquery" .` (same exclusions) returns nothing.

---

## 3. Architecture

This is a deletion-and-rewrite refactor, not an architecture change. The remaining architecture is the unchanged single-mode pipeline:

```
+---------------------------+
|        End User           |
| (terminal / shell / CI)   |
+-------------+-------------+
              |
              v
+---------------------------+
|      Click CLI Layer      |
|  fincli/app/cli.py        |
+-------------+-------------+
              |
              v
+---------------------------+
|    Orchestration Layer    |
|    fincli/app/main.py     |
+-------------+-------------+
              |
              v
+---------------------------+
|   Screener pipeline       |
|   (Finviz HTML scrape)    |
|   cfscrape + BS4          |
+-------------+-------------+
              |
              v
       Finviz.com (Cloudflare-protected HTML)
```

Cross-cutting (unchanged): `core/configuration/`, `config/config.py`, `logger/logger.py`, `singleton.py`.

### 3.0 Classification

"Removing `fundainsight`" decomposes into three independent dimensions, each addressed in a different section of this spec:

1. **Python import package** (`fundainsight/` directory, `python -m fundainsight`) — addressed by deletion in §3.1 + §5.1 Commit 3.
2. **Distribution package metadata** (`pyproject.toml` `[project] name`, currently `"finscrape"`) — addressed by rename in §3.2 + §5.1 Commit 4. The distribution name was historically `"finscrape"`, not `"fundainsight"`, so this dimension is technically a sibling rename rather than a fundainsight removal.
3. **Product / docs language** ("two-mode CLI", `fundainsight/` references in prose) — addressed by full single-mode rewrite in §6.

These three dimensions are addressed independently. The verification grep in §7.2 covers dimensions 1 and 3; the metadata-honesty check in §10 covers dimension 2.

### 3.1 Deletion Table

| Path | Type | Deleted because |
|---|---|---|
| `fundainsight/` | package | Out-of-scope product (fundamental analysis); the user is reducing the project to the screener. |
| `wisdom_fruit/` | package | Experimental, abandoned; never on the runtime path. Already documented as cleanup-queued in `CLAUDE.md`. |
| `shared/` | package | Empty scaffold left by a prior reorganization. |
| `example/` | package | Empty scaffold left by a prior reorganization. |
| `src/` | package | Empty scaffold (specifically `src/finpack/`) left by a prior reorganization. |
| `benchmarks/` | package | Empty scaffold; not on the runtime path. |

`tests/`, `workspace_output/`, `workspace_materials/`, `logs/` are untouched (they are gitignored or intentionally empty).

### 3.2 Edit Table (code & metadata only — docs handled in §6)

| File | Change |
|---|---|
| `core/configuration/configurator.py` (line 17) | Replace literal string `'fundainsight'` with `'fincli'` so `--history` resolves to `fincli/local_history/filter_history.json`. |
| `pyproject.toml` `[project] name` | `"finscrape"` -> `"fincli"`. |
| `pyproject.toml` `[project] dependencies` | Remove `"yahooquery"`. |
| `pyproject.toml` `[tool.mypy] files` | Remove `"fundainsight"`. Resulting list: `["fincli", "core", "config", "logger"]`. |
| `pyproject.toml` `[tool.ruff] extend-exclude` | Remove `"wisdom_fruit"`, `"shared"`, `"example"`, `"src"`, `"benchmarks"` (they no longer exist; the entries become noise). Keep `"workspace_output"`, `"workspace_materials"`, `"dist"`, `"htmlcov"`, `"__pycache__"`, `".venv"`. |
| `requirements.txt` | Remove the `yahooquery` line (and the commented `#yfinance` line if present). Keep `urllib3<2`. |
| `run.sh` | Simplify to launch `fincli` directly (no menu between two modes). |
| `run.bat` | Same simplification for Windows. |
| `.gitignore` | Audit for and remove any `fundainsight/`-only entries (e.g. `fundainsight/local_history/`). Keep `fincli/local_history/` if present; add it if not. |
| `pyproject.toml` (`[tool.setuptools.packages.find]` + `[tool.setuptools] py-modules`) | Add explicit package-discovery directive so flat-layout repo installs cleanly under modern setuptools. Pre-existing condition unblocked here. |
| `fincli/cli/cli_stock_screener.py` (Commit 13) | Replace `display_options` + `get_filters_indices` with a single `prompt_section` helper that displays each filter group with per-section local 1-based numbering, reprompts on bad input, and accepts blank-Enter as "skip this section." Apply `ruff format`. |

### 3.3 New Files (created during implementation)

| Path | Purpose |
|---|---|
| `docs/refactoring/cli-entry-point-spec.md` | Future-work spec: add `[project.scripts] fincli = "fincli.app.cli:cli"` so `pip install -e .` exposes a `fincli` shell command. Content shape per `docs/refactoring/README.md`. |
| `docs/refactoring/history-path-config-spec.md` | Future-work spec: move the `--history` filter-cache path into `Config` instead of hard-coding the module name in `configurator.py`. Content shape per `docs/refactoring/README.md`. |

### 3.4 Files NOT Touched

- `fincli/` source — all of it. No behavior change.
- `core/` source — except the one-line `configurator.py:17` fix.
- `config/config.py`, `logger/logger.py`, `singleton.py` — untouched.
- `agents/` source — but role/rule **content** is rewritten per §6.
- `.claude/hooks/load-rules.js`, `.claude/hooks/post-edit.js`, `.claude/hooks/pre-read.js` — untouched. `.claude/hooks/utils.js` and `.claude/hooks/on-stop.js` were updated in Commit 10 to remove `fundainsight` references that were missed by the v1.0 pre-grep. (See Risk R3 in §9.)
- `.claude/settings.json`, `.claude/settings.local.json` — untouched.
- `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` body — banner only (per §6.3 sub-decision A).
- `docs/FEEDBACK-LOG.md` past entries — append-only.
- `tests/` folder layout — preserved per Phase 2 plan.
- `scripts/` — untouched.

---

## 4. API Contracts

### 4.1 Public CLI surface

- **`fincli`** — unchanged. Same options (`--history`/`--hist`, `--debug`), same exit codes, same CSV output schema. No backward-compatibility concern for `fincli` users.
- **`fundainsight`** — **removed entirely.** Anyone who was relying on `python -m fundainsight` or its CSV outputs (`funda_insight_result_*.csv`, `funda_insight_result_unfiltered_*.csv`) needs to fork the pre-refactor git history. This is a deliberate, user-approved removal of a public surface, not a rename. There is no migration path and none is offered.

### 4.2 Internal contracts

- `core/configuration/configurator.py:build_config(...)` — signature unchanged. The only change is the directory it reads/writes from for history. This is internal implementation, not part of any public API.
- All other importable surfaces under `fincli/`, `core/`, `config/`, `logger/` keep their signatures as documented in `CONTRACTS.md` §7. The `fundainsight/` entries in §7 of `CONTRACTS.md` are removed wholesale during the doc rewrite.

### 4.3 Configuration shape

- `Config` Pydantic model (`config/config.py`) — fields unchanged. `name` and `description` defaults may be updated as part of the doc-rewrite phase if they currently mention "Stock Screener CLI" specifically; no schema change.

### 4.4 Filter history JSON

- **Path change**: `fundainsight/local_history/filter_history.json` no longer exists. `fincli/local_history/filter_history.json` is the single source.
- **Schema unchanged**: `{filter_key: value_code}` JSON, same as before.

---

## 5. Tasks by Agent

### 5.1 BACKEND (single implementer, ordered commits)

The order below is **load-bearing** — see §7 for rationale and §8 for verification.

1. **Commit 1 — Delete abandoned scaffolds.**
   - `git rm -r wisdom_fruit/ shared/ example/ src/ benchmarks/`.
   - Edit `pyproject.toml`: remove the `wisdom_fruit`, `shared`, `example`, `src`, `benchmarks` entries from `[tool.ruff] extend-exclude`.
   - Verify `ruff check .` and `ruff format --check .` still pass.
   - Verify no tracked automation file hardcodes the string `fundainsight`. Specifically grep `package.json`, `package-lock.json`, `run.sh`, `run.bat`, `scripts/**`, and (if any of these exist) `.pre-commit-config.yaml`, `.github/workflows/*`, `Makefile`, `justfile`, `tox.ini`, `noxfile.py`. The repo currently has only `package.json`, `package-lock.json`, `run.sh`, `run.bat`, and `scripts/`; the others are absent and need not be created. If any tracked file *outside the §3.2 edit table* hardcodes `fundainsight`, surface back to ARCH before proceeding rather than self-deciding the fix.

2. **Commit 2 — Fix `core/configuration/configurator.py:17` (BEFORE deleting `fundainsight/`).**
   - Edit line 17: replace `'fundainsight'` with `'fincli'`.
   - Verify `python -m fundainsight --history` still works against existing fundainsight history (cross-mode read is now broken — that is fine, fundainsight is about to be deleted; this is a safety swap so `fincli --history` does not break in commit 3).
   - This is the only Python source-code change in the entire refactor.

3. **Commit 3 — Delete `fundainsight/` + drop `yahooquery` and `fundainsight` from project metadata.**
   - `git rm -r fundainsight/`.
   - Edit `pyproject.toml`:
     - Remove `"yahooquery"` from `[project] dependencies`.
     - Remove `"fundainsight"` from `[tool.mypy] files`. Resulting: `["fincli", "core", "config", "logger"]`.
   - Edit `requirements.txt`: remove the `yahooquery` line. Keep `urllib3<2`.
   - Verify `python -m fincli --history` works and reads from `fincli/local_history/filter_history.json`.

4. **Commit 4 — Rename project: `finscrape` -> `fincli`.**
   - Edit `pyproject.toml` `[project] name`: `"finscrape"` -> `"fincli"`.
   - Re-install: `pip install -e ".[dev]"` from a clean venv to confirm the rename takes effect.

5. **Commit 5 — Simplify launchers and audit `.gitignore`.**
   - Edit `run.sh`: drop the menu; invoke `python -m fincli` with passthrough args.
   - Edit `run.bat`: same simplification for Windows.
   - Audit `.gitignore` for `fundainsight/`-only entries; remove them. Ensure `fincli/local_history/` is gitignored (add the entry if missing).

6. **Commit 6 — Top-level + `docs/` rewrite.**
   - Rewrite in full per §6 of this spec: `README.md`, `ARCHITECTURE.md`, `CLAUDE.md`, `CONTRACTS.md`, `TESTING.md`, `AGENTS.md`, `TOOLS_REFERENCE.md`, `docs/MODULE_REFERENCE.md`, `docs/THESIS.md`.
   - Apply the surgical updates to `CLAUDE.md` "Phase Status" Phase 2 body and "Tech Debt" entries (§6.3).
   - May be split into 2 commits if size warrants — implementer's call.

7. **Commit 7 — Rewrite `agents/rules/*.md` (5 files) + `agents/roles/*.md` (8 files), and add the banner to the harness rollout spec.**
   - Full single-mode rewrite per §6.4.
   - Banner-only edit on `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md` per §6.5 (exact text reproduced there).

8. **Commit 8 — Append entry to `docs/FEEDBACK-LOG.md`.**
   - One new entry dated 2026-05-04, summarizing this refactor and linking to this spec. Past entries untouched.

9. **Commit 9 — Add the two follow-up specs at `docs/refactoring/`.**
   - `docs/refactoring/cli-entry-point-spec.md` — future-work spec for adding a `[project.scripts] fincli = "fincli.app.cli:cli"` entry point.
   - `docs/refactoring/history-path-config-spec.md` — future-work spec for moving the history path into `Config`.
   - Both follow naming convention `<topic>-spec.md` per `docs/refactoring/README.md`.

10. **Commit 10 — Retarget agent harness hooks to single-mode (Risk R3 follow-through).**
    - Edit `.claude/hooks/utils.js`:
      - Remove the `fundainsight` SERVICES entry (lines 62-67 in pre-Commit-10 state).
      - Update dependency arrays to drop `'fundainsight'` from each: `core: ['fincli']`, `config: ['fincli']`, `logger: ['fincli']`. Drop the `fincli: ['fundainsight']` entry entirely (fincli has no remaining service dependencies).
      - Remove the two `/fundainsight\/...` regex patterns (lines 205 and 210 in pre-Commit-10 state).
    - Edit `.claude/hooks/on-stop.js`:
      - Update the comment on line 224 from `editing core → also test fincli, fundainsight` to `editing core → also test fincli`.
      - Update the mypy command on line 269 from `'mypy fundainsight fincli core config logger'` to `'mypy fincli core config logger'`.
    - Verify the hooks still parse: `node -c .claude/hooks/utils.js` and `node -c .claude/hooks/on-stop.js` (or equivalent — the actual hooks are loaded by the harness, not directly executed; a syntax check is sufficient).
    - This commit closes Risk R3.

11. **Commit 11 — Fix flat-layout setuptools auto-discovery for installable build.**
    - Edit `pyproject.toml` to add a `[tool.setuptools.packages.find]` directive so setuptools knows which top-level packages to install:

      ```toml
      [tool.setuptools.packages.find]
      include = ["fincli*", "core*", "config*", "logger*"]
      ```

      Plus `py-modules = ["singleton"]` under `[tool.setuptools]` to expose `singleton.py` as a top-level module.
    - Verify with `pip install -e ".[dev]"` from a clean venv. The §7.2 acceptance assertions then become checkable.
    - This commit unblocks §10 acceptance and §7.2 install-row.
    - This commit is **classified** as scope-creep relative to v1.0 — it fixes a pre-existing condition. The user's pre-authorization explicitly covers ARCH amendments needed to reach the spec's stated acceptance criteria, so authorizing this commit is in-scope.

13. **Commit 13 — Fix CLI section-prompt + bounds-checked input (post-validation scope expansion).**
    - Edit `fincli/cli/cli_stock_screener.py`:
      - Replace `display_options` and `get_filters_indices` (broken pair where display numbers diverged from dict positions, producing silent miscoordination on items 5–9 and `IndexError` on inputs >29) with a single `prompt_section` helper. The helper displays one filter group at a time using **per-section local 1-based numbering** (so a typed number always maps to its position in the group's `grouped_keys` list), reprompts on non-integer or out-of-range input, and treats blank input as "skip this section."
      - Update `select_filters_and_values` to invoke `prompt_section` three times (Fundamental, Descriptive, Technical) instead of the previous single combined prompt.
      - Apply `ruff format` to the file (was inconsistent with `[tool.ruff.format] quote-style = "double"`). All format deltas are mechanical; no semantic changes outside the new helper.
    - This is a behavior-fixing commit, classified as scope-creep relative to v1.0–v1.2 §2.2 N4 (now amended in v1.3). The fix was authorized inline by the user after live happy-path testing surfaced the bug; it is not a free-standing improvement.
    - Verify `python -m fincli` runs the new section-by-section flow against live Finviz and produces a `workspace_output/stock_screener_<timestamp>.csv`. (User confirmed: working.)

### 5.2 FRONTEND, UX_UI

Not invoked. No UI surface.

### 5.3 QA

Post-implementation only. Validates the §8 verification checklist; spot-checks doc rewrites for residual `fundainsight` / `yahooquery` mentions; confirms `python -m fincli` happy path produces the expected CSV.

### 5.4 REVIEWER

Post-implementation only. Pays attention to:

- Commit ordering matches §7 (configurator fix before `fundainsight/` deletion).
- Doc rewrites are full single-mode rewrites (Q3 = Option B), not surgical edits with leftover two-mode language.
- `CLAUDE.md` "Phase Status" and "Tech Debt" updates landed exactly as specified in §6.3.
- `FEEDBACK-LOG.md` past entries are unmodified.
- The two follow-up specs at `docs/refactoring/` exist and conform to the README convention.
- The harness rollout spec banner is present and verbatim per §6.5.
- No new `fundainsight` or `yahooquery` strings anywhere outside the banner.

---

## 6. Spec Updates

### 6.1 Files rewritten in full (Q3 = Option B)

For each file below, the implementer treats it as a fresh single-mode CLI doc. Section structure may change. Two-mode tables collapse to plain prose. Goal: no future reader can tell this used to be a two-product repo.

| File | Substantive change |
|---|---|
| `README.md` | Drop two-mode framing. Replace with single-mode "what is fincli / how to install / how to run / where output lands" narrative. Drop `fundainsight` and `yahooquery` references entirely. |
| `ARCHITECTURE.md` | Remove the `fundainsight` data flow, the Yahoo Finance integration section, the threading-model bullet about `ThreadPoolExecutor`, the `fundainsight/` row of the module map, and the `fundainsight/` block of the folder tree. The remaining diagram + module map describe only the screener pipeline. |
| `CLAUDE.md` | Drop `fundainsight` from the Project Overview (now a single-mode CLI: just the Finviz screener). Remove all `fundainsight/`, `yahooquery`, ThreadPoolExecutor, and `equity_calc.adjust_assets` references from "Important Files", "Conventions", "Common Gotchas", "Known Issues / Tech Debt". Apply the surgical "Phase Status" and "Tech Debt" deltas from §6.3 below. |
| `CONTRACTS.md` | Remove §1.2 (`fundainsight` CLI), §3 (Yahoo Finance data shape contract), §4.2 / §4.3 (`funda_insight_result_*` CSV schemas), and the §7.2 / §7.3 / §7.4 / §7.5 entries (fundainsight importable surfaces). Renumber remaining sections. The `fundainsight/local_history/` mention in §5.3 is also removed. |
| `TESTING.md` | Phase 2 scope changes from `fundainsight/calculators/` to `fincli/stock_screening/` + the screener pipeline. Remove the `test_picker_pipeline.py`, `test_equity_calc.py`, and Yahoo fixture references from the layout. Remove the `equity_calc.adjust_assets` `not int` bug entry from "Known Gaps" (file is gone). Update the example mock test to use a fincli fixture instead of yahooquery. |
| `AGENTS.md` | Update Tier 4 module list: remove `fundainsight/` row. Update doc-fingerprint references (e.g., MODULE_REFERENCE.md description) to single-mode. Update Change Log with a 2026-05-04 entry summarizing the single-mode reduction. |
| `TOOLS_REFERENCE.md` | Drop `yahooquery` patterns; keep Click, pandas, Pydantic, cfscrape, BeautifulSoup4 patterns. |
| `docs/MODULE_REFERENCE.md` | Remove `fundainsight/` and its sub-modules entirely. Keep `fincli/`, `core/`, `config/`, `logger/` entries. |
| `docs/THESIS.md` | Update the product framing (now a single-mode screener CLI). Update roadmap: drop fundamental-analysis aspirations or move them to a "Historical scope" section if the implementer prefers. The "current phase" remains Phase 1 of the harness rollout (just merged) followed by this single-mode reduction. |

### 6.2 Append-only edits

| File | Edit |
|---|---|
| `docs/FEEDBACK-LOG.md` | **Append** a new entry dated `### 2026-05-04 — Reduce algo_beta to fincli only`. Body summarizes: removal of `fundainsight/` + abandoned scaffolds, retention of `core/`/`config/`/`logger/`/`singleton.py`/agent harness, and links to `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` for the formal record. **Do not edit any prior entry.** |

### 6.3 Surgical updates inside `CLAUDE.md`

Beyond the broader rewrite in §6.1, two specific in-document updates are required:

**"Phase Status" table** — Phase 2's body changes from:

> "Introduce real `pytest` test suite for `fundainsight/calculators/`, `core/configuration/`, and the screener pipeline. Add HTML / yahooquery fixtures. Add type hints incrementally to the modules being tested — driving the mypy advisory count down. Fix the `equity_calc.adjust_assets` `not int` bug as part of writing its tests."

to:

> "Introduce real `pytest` test suite for `fincli/stock_screening/` and the screener pipeline. Add HTML fixtures. Add type hints incrementally to the modules being tested — driving the mypy advisory count down."

Phases 1, 3, 4 stay as written.

**"Known Issues / Tech Debt"** — two specific deltas:

- **Drop entirely**: the `equity_calc.adjust_assets()` `not int` truthy-check bug entry. The file is gone; the bug is gone with it. Do not move it elsewhere.
- **Rewrite**: the "Hard-coded history path in `core/configuration/configurator.py`" entry. Old text says "Phase 2 fix candidate." New text says: the literal swap is now done (`'fundainsight'` -> `'fincli'`); the deeper Config-driven fix is tracked at `docs/refactoring/history-path-config-spec.md`.

Other tech-debt entries that referenced `fundainsight` (e.g. "Hardcoded filters in `picker.py`") are dropped since the file is gone.

### 6.4 `agents/` retargeting

All five `agents/rules/*.md` files and all eight `agents/roles/*.md` files are rewritten in full to remove `fundainsight`, `yahooquery`, and ThreadPoolExecutor references. Examples that anchored test cases to `equity_calc.adjust_assets` are reanchored to a `fincli` example (e.g. `convert_market_cap_to_numeric` in `fincli/app/main.py`). The role roster (8 roles) is unchanged.

### 6.5 Harness rollout spec banner (sub-decision A)

Add **one new line at the very top** of `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`, immediately under the existing title heading. Exact text:

> **Note (2026-05-04):** Phase-2 scope in this spec referenced `fundainsight`. That module has since been removed. See `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md`; future Phase-2 work targets `fincli`'s test suite only.

The body of the spec is left intact as a historical record.

### 6.6 Two new follow-up specs

Created during Commit 9 (§5.1). Both follow the naming convention `<topic>-spec.md` per `docs/refactoring/README.md`. Their content is the BACKEND implementer's deliverable, not part of this spec.

| Path | Topic |
|---|---|
| `docs/refactoring/cli-entry-point-spec.md` | Future work: add `[project.scripts] fincli = "fincli.app.cli:cli"` so `pip install -e .` exposes a `fincli` shell command instead of requiring `python -m fincli`. Document the `cli` callable currently exists at `fincli/app/cli.py:run_main` (the implementer should confirm the exact attribute name during writing) and capture any rename needed. |
| `docs/refactoring/history-path-config-spec.md` | Future work: move the `--history` filter-cache path out of `core/configuration/configurator.py`'s hardcoded module-name string into a `Config`-driven setting (e.g. `history_dir: Path = Path("fincli/local_history")`). Includes migration considerations for any user with an existing `filter_history.json`. |

---

## 7. Sequencing & Verification

### 7.1 Settled commit ordering (load-bearing)

1. Delete abandoned scaffolds (`wisdom_fruit/`, `shared/`, `example/`, `src/`, `benchmarks/`) + remove their `[tool.ruff] extend-exclude` entries.
2. **Fix `core/configuration/configurator.py:17` BEFORE deleting `fundainsight/`** — prevents a runtime `FileNotFoundError` on `fincli --history` in any intermediate snapshot.
3. Delete `fundainsight/`. In the same commit: drop `fundainsight` from `[tool.mypy] files` and drop `yahooquery` from `pyproject.toml` deps + `requirements.txt`.
4. Rename package: `finscrape` -> `fincli` in `pyproject.toml`.
5. Edit launchers (`run.sh`, `run.bat`) simplified to fincli-only. Audit `.gitignore` for fundainsight-only entries.
6. Top-level + `docs/` rewrite (single commit or split if size warrants).
7. `agents/rules/*.md` + `agents/roles/*.md` rewrite + add banner to `docs/superpowers/specs/2026-05-02-agent-harness-replication-design.md`.
8. Append entry to `docs/FEEDBACK-LOG.md`.
9. Add the two follow-up specs at `docs/refactoring/`.

### 7.2 Settled verification checklist (post-merge)

| Check | Pass condition |
|---|---|
| `python -m fincli --debug` | Runs, prompts for filters, writes CSV. No import errors. |
| `python -m fincli --history` | Reads `fincli/local_history/filter_history.json` (creates dir if missing). **Regression check for the configurator fix.** |
| `ruff check .` | Exit 0. |
| `ruff format --check .` | Exit 0. |
| `mypy fincli core config logger` | Same-or-fewer errors than pre-refactor baseline (Phase 1 advisory). |
| `pytest tests/` | Exit 0 (no test bodies; collects nothing). |
| `pip install -e ".[dev]"` from clean venv | Installs as `fincli`. `python -c "import fincli; import core; import config; import logger; import singleton"` succeeds. **After Commit 11 lands, the install must succeed in a fresh venv. The post-install `find_spec('fundainsight') is None` and `python -m fincli --help` checks (per Amendment A in v1.1) remain unchanged.** Additionally, after install in a fresh venv the implementer must run two further assertions to prove `fundainsight` is genuinely gone (not merely hidden by a stale cache) and that `fincli` is substantively functional, not merely importable: `python -c "import importlib.util; assert importlib.util.find_spec('fundainsight') is None, 'fundainsight is still importable'"` must exit 0, AND `python -m fincli --help` must exit 0 and show the Click usage banner. (Note: Q2 = Option B explicitly defers `[project.scripts] fincli = ...` to a follow-up spec, so the bare `fincli --help` shell command is NOT yet available post-refactor in v1.2; `python -m fincli --help` is the substantive smoke check that IS expected to work.) |
| `grep -r "fundainsight" .` (excl `.git`, `node_modules`, `workspace_output`, `__pycache__`) | Returns ONLY the one banner line on `2026-05-02-agent-harness-replication-design.md`. |
| `grep -r "yahooquery" .` (excl same) | Returns nothing. |
| `grep -ri -E "two modes\|two-mode\|python api\|library mode" *.md docs/` | Returns no matches OR each match is reviewed and judged "intentional historical residue" by the reviewer (e.g. content inside a journal entry on `FEEDBACK-LOG.md`). The check exists to catch broader two-mode framing language that the per-string `fundainsight`/`yahooquery` greps would not catch. |

---

## 8. Tests

No new test bodies in this refactor. Verification is operational (CLI smoke tests, lint, type-check, grep-based residual checks) per §7.2.

Phase 2 of the harness rollout owns introducing pytest test bodies, with scope updated by this refactor to `fincli/stock_screening/` + the screener pipeline (see §6.3 Phase Status update).

Coverage gate remains deferred to Phase 3 per `TESTING.md`. mypy remains advisory in Phase 1 per `TESTING.md`. Neither phase trigger is moved by this refactor.

---

## 9. Risks & Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Doc cross-link breakage — surviving docs may still link to `fundainsight`-section anchors that no longer exist after the rewrite. | Medium | Low | The `grep -r "fundainsight"` step in §7.2 catches lingering string references. The reviewer is briefed to spot-check `[…](#…)` links across rewritten docs. Broken links degrade reading quality but do not affect runtime. |
| R2 | `pip install -e .` cache on existing dev environments — developers with the project installed under the old `finscrape` distribution name may end up with two ghost installations after the rename. | Medium | Low | The installation step in §7.2 (`pip install -e ".[dev]"` from a clean venv) is the canonical fix. Document in the new `README.md` that existing dev environments should `pip uninstall finscrape` (and optionally `pip uninstall fincli` if a stale link exists) before reinstalling. |
| R3 | Harness hooks hardcode `fundainsight` — a JS hook somewhere in `.claude/hooks/` could break if it expected the directory to exist. | Low (closed) | Medium | The v1.0 pre-grep of `.claude/hooks/` missed two files: `utils.js` (SERVICES map + dependency arrays + 2 regex patterns) and `on-stop.js` (mypy command + comment). v1.2 amends to add Commit 10 which retargets both files. The risk now is closed. |

Additional minor risks already absorbed by the design:

- **Banner-only edit on the harness rollout spec** preserves historical record without confusing future readers — verified in §6.5.
- **`docs/FEEDBACK-LOG.md` append-only constraint** — explicitly called out in §6.2 to prevent the implementer from "tidying up" past entries during the rewrite pass.
- **Commit ordering load-bearing** — explicitly called out in §5.1 / §7.1; the configurator fix preceding `fundainsight/` deletion is the single non-obvious sequencing rule.

---

## 10. Acceptance Criteria

A reviewer can declare this refactor complete when **all** of the following are simultaneously true:

- **Behavior**: `python -m fincli --debug` and `python -m fincli --history` both run end-to-end producing the expected CSV; the latter reads from `fincli/local_history/filter_history.json`.
  - Sub-bullet: The interactive filter-selection flow proceeds **section-by-section** (Fundamental → Descriptive → Technical). Each section's numbers are local 1-based indices into that section's filters; blank input skips a section; out-of-range or non-integer input reprompts with a clear error message (no `IndexError`). Verified live by the user 2026-05-04 against `refactor/fincli-only @ c997224`.
- **Project metadata**: `pyproject.toml` ships as `name = "fincli"`, lacks `yahooquery` in `[project] dependencies`, lacks `fundainsight` in `[tool.mypy] files`, and lacks the abandoned-scaffold names in `[tool.ruff] extend-exclude`. `requirements.txt` lacks `yahooquery` and keeps `urllib3<2`.
- **Filesystem**: `fundainsight/`, `wisdom_fruit/`, `shared/`, `example/`, `src/`, `benchmarks/` are absent. `fincli/`, `core/`, `config/`, `logger/`, `singleton.py`, `agents/`, `docs/`, `.claude/`, `tests/` (structure only) are present.
- **Tooling**: `ruff check .`, `ruff format --check .`, `pytest tests/` all exit 0. `mypy fincli core config logger` reports same-or-fewer errors than baseline.
- **Documentation**: All files listed in §6.1 read as fresh single-mode CLI docs. `CLAUDE.md` Phase 2 body and Tech Debt section reflect §6.3 deltas exactly. `docs/FEEDBACK-LOG.md` has one new dated 2026-05-04 entry; prior entries unchanged.
- **Harness retargeting**: All `agents/rules/*.md` (5) and `agents/roles/*.md` (8) are single-mode. The harness rollout spec carries the §6.5 banner verbatim and nothing else changed in its body.
- **Follow-ups**: `docs/refactoring/cli-entry-point-spec.md` and `docs/refactoring/history-path-config-spec.md` exist, follow `<topic>-spec.md` naming, and describe their respective deferred work.
- **Residuals**: `grep -r "fundainsight" .` returns only the harness-spec banner. `grep -r "yahooquery" .` returns nothing.

---

## 11. Assumptions and Open Questions

### 11.1 Assumptions

- **A1** No external user / downstream automation depends on `python -m fundainsight` or its CSV outputs. The user has confirmed this in the brainstorm: removal is intentional and final.
- **A2** The pre-refactor mypy baseline is captured by running `mypy fincli fundainsight core config logger` on the pre-refactor branch and recording the exact error count *before* Commit 1 begins. The post-refactor `mypy fincli core config logger` must report a count that is "same or fewer" relative to that recorded baseline, after accounting for the disappearance of the `fundainsight` rows. The implementer captures the baseline count in the PR description so reviewers can verify the comparison without needing to check out the pre-refactor SHA. (Renumbered from A3 in v1.2 after the original A2 was dropped — its assertion that hooks did not hardcode `fundainsight` proved wrong; Commit 10 now handles the cleanup.)
- **A3** `CLAUDE.md`'s "history path" tech-debt entry currently reads as "Phase 2 fix candidate." If the entry has already been edited or removed by another commit before this refactor lands, the implementer surfaces back to ARCH before applying the §6.3 rewrite. (Renumbered from A4 in v1.2.)
- **A4** The two follow-up specs are deliberately stub-quality at creation time. Their detailed design happens later when the user is ready to action them. (Renumbered from A5 in v1.2.)

### 11.2 Open Questions

None blocking. The brainstorm closed every meaningful decision.

### 11.3 Non-Blocking Questions (deferred to follow-up specs)

- Exact callable to expose at `[project.scripts] fincli` — answered in `docs/refactoring/cli-entry-point-spec.md`.
- Migration UX for users with an existing `fundainsight/local_history/filter_history.json` — none is offered; deletion is final. If demand surfaces, captured as a future addition to `docs/refactoring/history-path-config-spec.md`.

---

## 12. Next Steps

1. **HUMAN review** of this spec and the companion `arch-conversation-fincli-only-refactor.txt` file at the repo root.
2. On approval, **HANDOFF_TO BACKEND** to execute §5.1 in commit order.
3. **VERIFIER** runs §7.2 verification checklist post-implementation.
4. **REVIEWER** validates §5.4 review attention points.
5. **QA** validates §10 acceptance criteria.
6. **HUMAN** closes out the refactor.

HANDOFF_TO: HUMAN (then BACKEND on approval)

---

### 13. Lessons Learned (added 2026-05-04 in v1.3)

The v1.2 validation cycle completed with VERIFIER returning VERIFIED, REVIEWER returning APPROVE_WITH_NITS, and QA returning PASS — but only because QA elected Path B (deferred the live interactive happy-path to the user). On the user's first live run, an `IndexError` surfaced in `fincli/cli/cli_stock_screener.py` that had been latent in master since before this branch existed. The validation cycle's grep-and-import-based smoke checks could not have caught it because the bug was in a runtime-interactive code path with no automated coverage.

Two takeaways captured here for future refactors:

1. **A "Behavior" acceptance criterion that requires a live network round-trip should not be deferred to the user without the user explicitly opting in.** When QA reports Path B, the orchestrator should treat that as a pending acceptance check, not a closed one — and the user should be invited to validate before any "ready to merge" claim, not after.
2. **Refactor specs that say "no behavior change in the kept code" should still require a 30-second smoke of the kept code's user-facing surface.** A refactor can pass every grep, lint, and type check while leaving a years-old user-facing bug unmasked. The §7.2 Amendment-A clean-venv check (added in v1.1) caught import-time failures; an analogous "interactive smoke" check would have caught this. Captured as a forward-looking item for the test scaffolding that Phase 2 of the harness rollout owns.
