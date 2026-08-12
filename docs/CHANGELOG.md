# Fin CLI — Shipped-Work Changelog

A thin, newest-first index of shipped streams. Phase status and direction live
in `docs/THESIS.md`; implementation detail lives in the linked spec or closeout.
Per-merge history does not belong in `CLAUDE.md`.

- 2026-08-11 · `scrape_link` on `POST /screens` · accept a direct Finviz URL on the HTTP API, mirroring the CLI's `--scrape-link` (mutually exclusive with `filters`, no inventory validation, host-allowlisted to finviz.com); also grows the filter inventory with `fa_sales3years` and the missing `ta_perf2` 3/5/10-year value codes · `docs/pendingwork/2026-07-25-scrape-link-http-api.md`
- 2026-08-11 · Parser hardening · fix GitHub issue #14 (redesigned-layout ticker cells duplicating their first letter) and close MAJOR #4 (missing-table HTML silently coercing to a 200 empty result) via `ScreenerLayoutError` + the `js-screener-body-empty` empty-result discriminator · GitHub issue #14
- 2026-08-11 · Observability · request-id correlation, JSON logs, health triad + `/metrics` on the HTTP API; CLI `run_id` (Singleton-logger correlation deferred — THESIS "Beyond Phase 4") · `docs/plans/2026-07-14-observability.md`
- 2026-07-31 · Harness quality gates · promote aggregate coverage (90%) and strict mypy to blocking Stop-hook gates, reach strict-mypy zero with no suppressions, and correct the document-role split · `docs/refactoring/archive/harness-quality-gates-burndown-spec.md`
- 2026-06-27 · Launcher cleanup · remove broken shell launchers and standardize installed entry points · `docs/FEEDBACK-LOG.md`
- 2026-05-24 · HTTP API · add the FastAPI surface and committed OpenAPI contract · `docs/superpowers/specs/archive/2026-05-22-fincli-api-design.md`
- 2026-05-21 · Filter inventory · add `--list-filters --json` and polyglot integration guidance · `docs/features/archive/list-filters-spec.md`
- 2026-05-16 · Pipeline mode · add structured inputs, deterministic outputs, stream discipline, and classified exits · `docs/features/archive/pipeline-mode-spec.md`
- 2026-05-06 · Entry-point and history portability · ship installed CLI entry point and Config-owned history path · `docs/refactoring/archive/cli-entry-point-spec.md`
- 2026-05-04 · Single-mode reduction · remove the retired fundamental-analysis path and keep Fin CLI focused on screening · `docs/superpowers/specs/archive/2026-05-04-fincli-only-refactor-design.md`
- 2026-05-02 · Agent harness · install the documentation spine, roles, rules, hooks, and Python tooling · `docs/superpowers/specs/archive/2026-05-02-agent-harness-replication-design.md`
