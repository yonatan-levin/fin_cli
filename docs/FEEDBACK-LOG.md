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

### 2026-05-04 — Reduce algo_beta to fincli only

**What:** The codebase is now a single-mode CLI (the Finviz screener under `fincli/`). The previously-bundled `fundainsight/` fundamental-analysis package and the abandoned scaffolds (`wisdom_fruit/`, `shared/`, `example/`, `src/`, `benchmarks/`) were deleted wholesale. Shared infrastructure (`core/`, `config/`, `logger/`, `singleton.py`) and the agent harness (`agents/`, `.claude/`, `docs/`) were preserved. The distribution name in `pyproject.toml` changed from `finscrape` to `fincli`; `yahooquery` was dropped from runtime dependencies; `urllib3<2` is preserved (cfscrape requires it).

**Why:** The user (Yonatan) explicitly chose to reduce scope to the screener only. The fundainsight pipeline carried known correctness bugs (`equity_calc.adjust_assets` `not int` truthy-check, hardcoded country/sector exclusions in `picker.py`) and depended on Yahoo Finance data quality that varied widely across international tickers. Continuing to maintain it alongside the harness rollout was higher cost than benefit. Removing it leaves a sharper, smaller surface for Phase 2 testing to target.

**How to apply:** Anyone resuming work should treat the codebase as a single-mode CLI. `python -m fundainsight` is gone permanently — no deprecation alias, no migration path. Anyone needing the analysis pipeline should fork the pre-refactor git history. The full refactor design lives at `docs/superpowers/specs/2026-05-04-fincli-only-refactor-design.md` (v1.1). Two stub follow-up specs (`docs/refactoring/cli-entry-point-spec.md`, `docs/refactoring/history-path-config-spec.md`) capture deferred work; their detailed design happens later when the user is ready to action them.

### 2026-05-06 — Console-script entry point (`fincli`)

**What:** Added `[project.scripts]` to `pyproject.toml` with target `fincli.app.cli:run_main`, exposing a bare `fincli` shell command on PATH after `pip install -e ".[dev]"`. The shipped spec moved to `docs/refactoring/archive/cli-entry-point-spec.md`.

**Why:** Removes the `python -m fincli` ergonomic wart that was the last open item from the 2026-05-04 single-mode reduction (Q2 / Option B). The change is non-breaking per CONTRACTS §7 — additive packaging metadata, no version bump, no signature change, no CLI option change. `python -m fincli`, `./run.sh`, and `run.bat` continue to work unchanged; the launchers intentionally retain `python -m fincli` for portability when the venv's `Scripts/` dir is not on PATH.

**How to apply:** The four "open decisions" in the stub spec were resolved without renaming `run_main` (it remains the entry-point target and is referenced by `fincli/__main__.py` and CONTRACTS §1/§6) and without anticipating subcommand expansion (Click's `@click.group(invoke_without_command=True)` already supports `run_main.add_command(...)` later without touching the entry-point target). Existing dev environments must re-run `pip install -e ".[dev]"` once for the new shell command to land on PATH.

### 2026-05-09 — Finpack surface deletion + stale-docs sweep

**What:** Deleted the entire abandoned `finpack` library surface in commit `d398111` (50 files / -6070 LOC): the `src/finpack/` package (26 files), 14 orphan tests that imported `from finpack`, 2 examples (`example/{advanced_usage,simple_usage}.py`), and 8 FinPack-only docs (`docs/api_reference.md`, `docs/configuration.md`, `docs/TROUBLESHOOTING_GUIDE.md`, `docs/FINPACK_TECHNICAL_PLAN.md`, `docs/LIBRARY_CONSOLIDATION_PROPOSAL.md`, `docs/MAINTENANCE_GUIDE.md`, `docs/MIGRATION_SUMMARY.md`, root `FINPACK_TRANSFORMATION_PLAN.md`). Then deleted 6 additional stale-direction artifacts in a follow-up sweep: `docs/ARCHITECTURE_DECISIONS.md` (351-line FinPack-consolidation ADR), `docs/ALTERNATIVE_DATA_SOURCES.md` (yfinance/Polygon-themed), `docs/ENHANCED_PROVIDERS_README.md` (multi-provider abstraction), `docs/REFACTORING_GUIDE.md` ("AlgoBeta Refactoring Guide" / picker.py migration), `.cursor/plans/finpack-two-step-screen-analyze-a24d54ce.plan.md` (abandoned FinPack Cursor plan), and `.cursor/rules/projectspec.mdc` (yfinance documentation links).

**Why:** Bug fix: `pytest tests/` produced 13 collection errors because the orphan test files imported from a `finpack` package that was never on the import path after the May-4 single-mode reduction. The README's claim "the pytest command runs cleanly because there is nothing to fail" was stale. After deletion, pytest collects 0 tests with 0 errors. The follow-up sweep removes the documentation contradictions that survived the package deletion: several adjacent docs (the M1/L1 items REVIEWER flagged on `d398111`) and one Cursor rule (`.mdc` extension, missed by REVIEWER's `.md`-pattern grep) still documented retired directions (`finpack`, `yfinance`, `yahooquery`, `Polygon`, "AlgoBeta", `picker.py`) and contradicted post-reduction reality. Per the docs-update Quality Rule 1: "a doc that lies is worse than no doc."

**How to apply:** The branch state is now coherent: the `finpack` direction is fully retired in source, tests, examples, and live docs. New references to `finpack`, `yfinance`, `yahooquery`, `Polygon`, "AlgoBeta", or `picker.py` in any LIVE doc should be treated as drift and fixed immediately. The conversation transcript (`arch-conversation-fincli-only-refactor.txt`) and historical specs in `docs/superpowers/specs/` retain finpack mentions in their immutable record — that's correct historical context, not drift. For future direction changes, follow this same pattern: delete the dead surface in one commit, sweep the docs in a follow-up, append a FEEDBACK-LOG entry capturing both. When grepping for stale references, include `.mdc` (Cursor rules) alongside `.md` (Markdown) — REVIEWER's pattern missed `projectspec.mdc` because of this.

### 2026-05-09 — History path now Config-driven

**What:** Replaced the hardcoded `os.path.realpath('fincli')` literal in `core/configuration/configurator.py` with a new `Config.history_dir: Path` field (default `Path("fincli/local_history")`). `build_config` now reads `config.history_dir / 'filter_history.json'`. The CLAUDE.md tech-debt + common-gotchas entries about this hardcode are struck. The shipped spec moved to `docs/refactoring/archive/history-path-config-spec.md`.

**Why:** Removes the last hardcoded path-construction in `Config`'s neighborhood. The 5 "open decisions" in the original stub were resolved in the planning phase: field name `history_dir`, type `pathlib.Path`, default `Path("fincli/local_history")` (relative — byte-equivalent to today), no migration helper (window closed), no `--history-dir` CLI flag (out of scope; deferred to `docs/reviewer/history-dir-cwd-portability.md`). Behavior is byte-identical for end users running from the repo root; the change exposes the directory as a Config field for future programmatic override.

**How to apply:** Anyone running `fincli --history` from a non-repo-root CWD continues to see the same FileNotFoundError as before — that's the limitation captured in the new reviewer note. Programmatic overrides via `Config(history_dir=Path("..."))` now work; future env-var or `--history-dir` wiring can build on top without touching the configurator.

### 2026-05-10 — CWD-portable history directory (platformdirs + HISTORY_DIR env)

**What:** `Config.history_dir` default now resolves via `platformdirs.user_data_dir("fincli")` instead of the CWD-relative `Path("fincli/local_history")`. This produces an absolute path under the user's data directory (`%LOCALAPPDATA%\fincli\local_history\` on Windows, `~/Library/Application Support/fincli/local_history/` on macOS, `~/.local/share/fincli/local_history/` on Linux). `core/configuration/configurator.py:build_config` also now reads a `HISTORY_DIR` env var as an override (un-namespaced, matching the existing `USE_HISTORY` convention). The reviewer note at `docs/reviewer/archive/history-dir-cwd-portability.md` has been archived. New runtime dep: `platformdirs`.

**Why:** Closes the CWD-portability follow-up from the 2026-05-09 history-path-config refactor. Before this change, `fincli --history` only worked from a directory containing a `fincli/` subdirectory — typically only the repo root. After: it works from any CWD. The `appauthor=False` kwarg is passed because platformdirs otherwise defaults `appauthor` to `appname`, producing a doubled `…\fincli\fincli\local_history` path on Windows; `False` collapses it to single-`fincli` symmetry across platforms. The 5 directions sketched in the reviewer note collapsed to options #2 + #3 (platformdirs default + env-var override); options #1, #4, #5 were rejected as either incorrect (#1 writes inside the read-only installed package) or scope creep (#4 adds CLI surface, #5 adds layered complexity).

**How to apply:** Existing dev environments must `pip install -e ".[dev]"` (or `pip install platformdirs`) once after pulling this commit. A pre-existing `fincli/local_history/filter_history.json` cache from the prior repo-root default will NOT be auto-migrated — the new default path is different. To preserve a cache, either copy the file to the new platformdirs path manually, or set `HISTORY_DIR=fincli/local_history` to point back at the old location. For most personal use, just regenerate the cache by going through the interactive flow once. Future env-var additions in this project should follow the un-namespaced UPPER_CASE_WITH_UNDERSCORES convention (no `FINCLI_` prefix) to match `USE_HISTORY` and `HISTORY_DIR`.

### 2026-05-11 — Restore `--scrape-link` CLI option

**What:** Re-added the `--scrape-link=<url>` Click option to `fincli/app/cli.py:run_main`. The option threads through `run_stock_screener(scrape_link=...)` → `build_config(scrape_link=...)` → `Config.scrape_link`. When `Config.scrape_link` is truthy, `run_stock_screener` short-circuits both the interactive filter picker and the Finviz query builder, using the supplied URL verbatim as the screener query. `--scrape-link` and `--history` are mutually exclusive — combining them raises a Click `UsageError`. CONTRACTS §1 re-documents the option in the Options table, the Behavior table (incl. the mutual-exclusion row), and the §6.1/§6.2 signatures. The first regression test for the project landed at `tests/unit/app/test_cli.py` (two `CliRunner` tests: option-accepted, mutual-exclusion). No URL validation is performed; cfscrape surfaces invalid-URL failures downstream. The shipped spec moved to `docs/features/archive/scrape-link-restoration-spec.md` (creating `docs/features/archive/`).

**Why:** The option existed historically in the now-deleted `fundainsight/` package (`@click.option('--scrape-link', default="", ...)` on `fundainsight/app/cli.py`). Commit `a840a1c` ("refactor: remove fundainsight package and yahooquery dependency", 2026-05-05) deleted the package and the decorator with it. The fincli-side `fincli/app/cli.py` never carried `--scrape-link`, so this is feature restoration on a different entry point, not a true revert. Evidence the loss was incidental rather than deliberate: `Config.scrape_link: str = ""` field still exists; CONTRACTS §4, ARCHITECTURE, README, and `docs/MODULE_REFERENCE.md` all describe the field; the May-4 reduction spec and FEEDBACK-LOG say nothing about removing the feature; no commit removed `Config.scrape_link` deliberately. The bypass-the-interactive-flow capability is a major productivity feature for the sole user, especially for re-running a saved Finviz URL.

**How to apply:** Existing dev environments need no reinstall — Click was already a runtime dependency and `CliRunner` is built into Click. Run the screener with `fincli --scrape-link=<finviz-url>` (or `python -m fincli --scrape-link=<url>`) to bypass the interactive picker. The sibling `--set-filters` JSON-input option (also lost in `a840a1c`) was explicitly deferred from this cycle per user direction; if needed, it can be restored separately following the same pattern. The new test file is the first real test body in the repo and seeds the Phase 2 testing direction at the CLI option-parsing layer; `tests/unit/app/test_cli.py` is collected and passes under the existing `pytest.ini_options` config without any new infrastructure.
