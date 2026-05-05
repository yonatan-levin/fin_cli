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
