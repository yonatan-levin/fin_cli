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
